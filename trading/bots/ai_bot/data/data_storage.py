"""
NEXUS AI TRADING SYSTEM - Data Storage for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/data/data_storage.py
Description: Module de stockage de données pour le bot AI.
             Supporte le stockage local (Parquet, CSV, HDF5),
             les bases de données (PostgreSQL, TimescaleDB, MongoDB),
             le cloud (AWS S3, GCP, Azure) et le cache (Redis).
             Gère la compression, le versionnement et l'archivage.
"""

import asyncio
import logging
import os
import json
import pickle
import gzip
import zlib
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd

# Stockage cloud (optionnel)
try:
    import boto3
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    boto3 = None

try:
    from google.cloud import storage
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False
    storage = None

try:
    from azure.storage.blob import BlobServiceClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    BlobServiceClient = None

# Base de données (optionnel)
try:
    import psycopg2
    from sqlalchemy import create_engine
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    psycopg2 = None
    create_engine = None

try:
    import pymongo
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    pymongo = None

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from shared.exceptions import StorageError
from shared.helpers.date_helpers import timestamp_to_datetime

# Configuration du logging
logger = logging.getLogger(__name__)


class StorageType(Enum):
    """Types de stockage."""
    LOCAL = "local"
    POSTGRES = "postgres"
    TIMESCALE = "timescale"
    MONGODB = "mongodb"
    REDIS = "redis"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    HDF5 = "hdf5"
    PARQUET = "parquet"
    CSV = "csv"
    PICKLE = "pickle"


class CompressionType(Enum):
    """Types de compression."""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    SNAPPY = "snappy"
    LZ4 = "lz4"
    ZSTD = "zstd"


@dataclass
class StorageConfig:
    """
    Configuration du stockage.
    """
    # Type de stockage principal
    primary_storage: StorageType = StorageType.LOCAL
    
    # Types de stockage secondaires (fallback)
    secondary_storage: List[StorageType] = field(default_factory=list)
    
    # Paramètres locaux
    local_path: str = "data/ai_bot/"
    local_format: str = "parquet"  # parquet, csv, hdf5, pickle
    
    # Paramètres PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database: str = "nexus_ai"
    postgres_user: str = "nexus"
    postgres_password: str = ""
    postgres_table_prefix: str = "ai_"
    
    # Paramètres MongoDB
    mongodb_host: str = "localhost"
    mongodb_port: int = 27017
    mongodb_database: str = "nexus_ai"
    mongodb_collection_prefix: str = "ai_"
    
    # Paramètres Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_ttl: int = 86400  # 24 heures
    
    # Paramètres AWS S3
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_prefix: str = "ai_bot/"
    
    # Paramètres GCP
    gcp_bucket: str = ""
    gcp_project: str = ""
    gcp_credentials: str = ""
    gcp_prefix: str = "ai_bot/"
    
    # Paramètres Azure
    azure_connection_string: str = ""
    azure_container: str = ""
    azure_prefix: str = "ai_bot/"
    
    # Paramètres de compression
    compression: CompressionType = CompressionType.GZIP
    compression_level: int = 6
    
    # Paramètres de versionnement
    enable_versioning: bool = True
    max_versions: int = 10
    version_format: str = "%Y%m%d_%H%M%S"
    
    # Paramètres d'archivage
    enable_archiving: bool = True
    archive_after_days: int = 90
    archive_path: str = "data/archive/"
    
    # Paramètres de performance
    batch_size: int = 1000
    async_write: bool = True
    use_cache: bool = True
    cache_size: int = 100
    cache_ttl: int = 300
    
    def __post_init__(self):
        """Validation des paramètres."""
        # Création des répertoires locaux
        if self.primary_storage == StorageType.LOCAL:
            Path(self.local_path).mkdir(parents=True, exist_ok=True)
            Path(self.archive_path).mkdir(parents=True, exist_ok=True)
        
        # Validation des credentials
        if self.primary_storage == StorageType.S3 and not self.s3_bucket:
            raise StorageError("s3_bucket requis pour S3")
        
        if self.primary_storage == StorageType.GCS and not self.gcp_bucket:
            raise StorageError("gcp_bucket requis pour GCS")
        
        if self.primary_storage == StorageType.AZURE and not self.azure_container:
            raise StorageError("azure_container requis pour Azure")


@dataclass
class StorageMetadata:
    """
    Métadonnées de stockage.
    """
    # Identifiants
    id: str
    name: str
    type: str
    created_at: datetime
    updated_at: datetime
    
    # Taille
    size: int = 0
    compressed_size: int = 0
    
    # Version
    version: int = 1
    version_history: List[str] = field(default_factory=list)
    
    # Métriques
    n_records: int = 0
    n_features: int = 0
    
    # Hash (intégrité)
    hash: str = ""
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'size': self.size,
            'compressed_size': self.compressed_size,
            'version': self.version,
            'version_history': self.version_history,
            'n_records': self.n_records,
            'n_features': self.n_features,
            'hash': self.hash,
            'tags': self.tags
        }


class DataStorage:
    """
    Gestionnaire de stockage de données pour le bot AI.
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        """
        Initialise le gestionnaire de stockage.
        
        Args:
            config: Configuration du stockage.
        """
        self.config = config or StorageConfig()
        
        # Connections
        self._connections: Dict[StorageType, Any] = {}
        self._cache: Dict[str, Tuple[datetime, Any]] = {}
        self._is_connected = False
        
        # Métadonnées
        self._metadata: Dict[str, StorageMetadata] = {}
        
        logger.info(f"DataStorage initialisé - Type: {self.config.primary_storage.value}")
        logger.info(f"Compression: {self.config.compression.value}")
        logger.info(f"Versionnement: {self.config.enable_versioning}")
    
    # ============================================================
    # CONNEXIONS
    # ============================================================
    
    async def connect(self) -> None:
        """
        Établit les connexions aux bases de données.
        """
        if self._is_connected:
            return
        
        logger.info("Établissement des connexions...")
        
        try:
            # PostgreSQL
            if self.config.primary_storage in [StorageType.POSTGRES, StorageType.TIMESCALE]:
                await self._connect_postgres()
            
            # MongoDB
            if self.config.primary_storage == StorageType.MONGODB:
                await self._connect_mongodb()
            
            # Redis
            if self.config.primary_storage == StorageType.REDIS:
                await self._connect_redis()
            
            # AWS S3
            if self.config.primary_storage == StorageType.S3:
                await self._connect_s3()
            
            # GCP
            if self.config.primary_storage == StorageType.GCS:
                await self._connect_gcp()
            
            # Azure
            if self.config.primary_storage == StorageType.AZURE:
                await self._connect_azure()
            
            self._is_connected = True
            logger.info("Connexions établies")
            
        except Exception as e:
            logger.error(f"Erreur de connexion: {e}")
            raise StorageError(f"Erreur de connexion: {e}")
    
    async def disconnect(self) -> None:
        """
        Ferme les connexions.
        """
        if not self._is_connected:
            return
        
        logger.info("Fermeture des connexions...")
        
        for storage_type, conn in self._connections.items():
            try:
                if storage_type in [StorageType.POSTGRES, StorageType.TIMESCALE]:
                    conn.close()
                elif storage_type == StorageType.MONGODB:
                    conn.close()
                elif storage_type == StorageType.REDIS:
                    conn.close()
            except Exception as e:
                logger.warning(f"Erreur de fermeture {storage_type.value}: {e}")
        
        self._connections.clear()
        self._is_connected = False
        logger.info("Connexions fermées")
    
    async def _connect_postgres(self) -> None:
        """Connecte à PostgreSQL/TimescaleDB."""
        if not POSTGRES_AVAILABLE:
            logger.warning("PostgreSQL non disponible")
            return
        
        conn_str = f"postgresql://{self.config.postgres_user}:{self.config.postgres_password}@{self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_database}"
        engine = create_engine(conn_str)
        self._connections[StorageType.POSTGRES] = engine
        
        # Vérification de la connexion
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        
        logger.info(f"Connecté à PostgreSQL: {self.config.postgres_database}")
    
    async def _connect_mongodb(self) -> None:
        """Connecte à MongoDB."""
        if not MONGODB_AVAILABLE:
            logger.warning("MongoDB non disponible")
            return
        
        client = pymongo.MongoClient(
            host=self.config.mongodb_host,
            port=self.config.mongodb_port
        )
        self._connections[StorageType.MONGODB] = client
        logger.info(f"Connecté à MongoDB: {self.config.mongodb_database}")
    
    async def _connect_redis(self) -> None:
        """Connecte à Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis non disponible")
            return
        
        client = redis.Redis(
            host=self.config.redis_host,
            port=self.config.redis_port,
            db=self.config.redis_db,
            decode_responses=False
        )
        self._connections[StorageType.REDIS] = client
        logger.info(f"Connecté à Redis: DB {self.config.redis_db}")
    
    async def _connect_s3(self) -> None:
        """Connecte à AWS S3."""
        if not AWS_AVAILABLE:
            logger.warning("AWS S3 non disponible")
            return
        
        session = boto3.Session(
            aws_access_key_id=self.config.s3_access_key,
            aws_secret_access_key=self.config.s3_secret_key,
            region_name=self.config.s3_region
        )
        s3 = session.client('s3')
        self._connections[StorageType.S3] = s3
        logger.info(f"Connecté à S3: {self.config.s3_bucket}")
    
    async def _connect_gcp(self) -> None:
        """Connecte à GCP."""
        if not GCP_AVAILABLE:
            logger.warning("GCP non disponible")
            return
        
        if self.config.gcp_credentials:
            client = storage.Client.from_service_account_json(
                self.config.gcp_credentials,
                project=self.config.gcp_project
            )
        else:
            client = storage.Client(project=self.config.gcp_project)
        
        self._connections[StorageType.GCS] = client
        logger.info(f"Connecté à GCS: {self.config.gcp_bucket}")
    
    async def _connect_azure(self) -> None:
        """Connecte à Azure."""
        if not AZURE_AVAILABLE:
            logger.warning("Azure non disponible")
            return
        
        client = BlobServiceClient.from_connection_string(
            self.config.azure_connection_string
        )
        self._connections[StorageType.AZURE] = client
        logger.info(f"Connecté à Azure: {self.config.azure_container}")
    
    # ============================================================
    # STOCKAGE PRINCIPAL
    # ============================================================
    
    async def store(
        self,
        data: Union[pd.DataFrame, np.ndarray, Dict, List],
        name: str,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StorageMetadata:
        """
        Stocke les données.
        
        Args:
            data: Données à stocker.
            name: Nom du dataset.
            tags: Tags pour catégorisation.
            metadata: Métadonnées supplémentaires.
            
        Returns:
            Métadonnées du stockage.
        """
        start_time = time.time()
        
        logger.info(f"Stockage de {name}")
        
        # Conversion des données
        df = self._to_dataframe(data)
        
        if df.empty:
            raise StorageError(f"Données vides pour {name}")
        
        # Génération de l'ID
        data_id = self._generate_id(name)
        
        # Compression
        compressed_data = self._compress_data(df)
        
        # Stockage selon le type
        if self.config.primary_storage == StorageType.LOCAL:
            path = await self._store_local(df, name, data_id)
        elif self.config.primary_storage in [StorageType.POSTGRES, StorageType.TIMESCALE]:
            path = await self._store_postgres(df, name, data_id)
        elif self.config.primary_storage == StorageType.MONGODB:
            path = await self._store_mongodb(df, name, data_id)
        elif self.config.primary_storage == StorageType.REDIS:
            path = await self._store_redis(df, name, data_id)
        elif self.config.primary_storage in [StorageType.S3, StorageType.GCS, StorageType.AZURE]:
            path = await self._store_cloud(df, name, data_id)
        else:
            raise StorageError(f"Type de stockage non supporté: {self.config.primary_storage}")
        
        # Métadonnées
        metadata_obj = StorageMetadata(
            id=data_id,
            name=name,
            type=self.config.primary_storage.value,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=len(compressed_data),
            compressed_size=len(compressed_data),
            n_records=len(df),
            n_features=len(df.columns),
            hash=self._calculate_hash(df),
            tags=tags or {}
        )
        
        # Sauvegarde des métadonnées
        await self._save_metadata(metadata_obj)
        
        # Cache
        if self.config.use_cache:
            self._cache[name] = (datetime.now(), df)
        
        logger.info(f"Stockage terminé: {name} - {len(df)} records, {time.time() - start_time:.3f}s")
        
        return metadata_obj
    
    async def load(self, name: str, version: Optional[int] = None) -> pd.DataFrame:
        """
        Charge les données.
        
        Args:
            name: Nom du dataset.
            version: Version spécifique.
            
        Returns:
            DataFrame des données.
        """
        logger.info(f"Chargement de {name}")
        
        # Vérification du cache
        if self.config.use_cache and name in self._cache:
            cache_time, cache_data = self._cache[name]
            if (datetime.now() - cache_time).seconds < self.config.cache_ttl:
                logger.debug(f"Cache hit pour {name}")
                return cache_data
        
        # Chargement selon le type
        if self.config.primary_storage == StorageType.LOCAL:
            df = await self._load_local(name, version)
        elif self.config.primary_storage in [StorageType.POSTGRES, StorageType.TIMESCALE]:
            df = await self._load_postgres(name, version)
        elif self.config.primary_storage == StorageType.MONGODB:
            df = await self._load_mongodb(name, version)
        elif self.config.primary_storage == StorageType.REDIS:
            df = await self._load_redis(name, version)
        elif self.config.primary_storage in [StorageType.S3, StorageType.GCS, StorageType.AZURE]:
            df = await self._load_cloud(name, version)
        else:
            raise StorageError(f"Type de stockage non supporté: {self.config.primary_storage}")
        
        # Mise en cache
        if self.config.use_cache and not df.empty:
            self._cache[name] = (datetime.now(), df)
        
        return df
    
    async def delete(self, name: str, version: Optional[int] = None) -> bool:
        """
        Supprime les données.
        
        Args:
            name: Nom du dataset.
            version: Version spécifique.
            
        Returns:
            True si supprimé.
        """
        logger.info(f"Suppression de {name}")
        
        # Suppression selon le type
        if self.config.primary_storage == StorageType.LOCAL:
            result = await self._delete_local(name, version)
        elif self.config.primary_storage in [StorageType.POSTGRES, StorageType.TIMESCALE]:
            result = await self._delete_postgres(name, version)
        elif self.config.primary_storage == StorageType.MONGODB:
            result = await self._delete_mongodb(name, version)
        elif self.config.primary_storage == StorageType.REDIS:
            result = await self._delete_redis(name, version)
        elif self.config.primary_storage in [StorageType.S3, StorageType.GCS, StorageType.AZURE]:
            result = await self._delete_cloud(name, version)
        else:
            result = False
        
        # Suppression du cache
        if name in self._cache:
            del self._cache[name]
        
        return result
    
    # ============================================================
    # STOCKAGE LOCAL
    # ============================================================
    
    async def _store_local(self, df: pd.DataFrame, name: str, data_id: str) -> str:
        """Stocke localement."""
        path = Path(self.config.local_path) / f"{data_id}.{self.config.local_format}"
        
        if self.config.local_format == "parquet":
            df.to_parquet(path, compression=self.config.compression.value)
        elif self.config.local_format == "csv":
            df.to_csv(path, index=False)
        elif self.config.local_format == "hdf5":
            df.to_hdf(path, key='data', mode='w')
        elif self.config.local_format == "pickle":
            with open(path, 'wb') as f:
                pickle.dump(df, f)
        else:
            raise StorageError(f"Format local non supporté: {self.config.local_format}")
        
        # Versionnement
        if self.config.enable_versioning:
            version_path = Path(self.config.local_path) / f"{data_id}_v{self._get_next_version(name)}.{self.config.local_format}"
            await self._copy_file(path, version_path)
        
        return str(path)
    
    async def _load_local(self, name: str, version: Optional[int] = None) -> pd.DataFrame:
        """Charge depuis le stockage local."""
        data_id = self._generate_id(name)
        
        if version is not None:
            path = Path(self.config.local_path) / f"{data_id}_v{version}.{self.config.local_format}"
        else:
            path = Path(self.config.local_path) / f"{data_id}.{self.config.local_format}"
        
        if not path.exists():
            raise StorageError(f"Fichier non trouvé: {path}")
        
        if self.config.local_format == "parquet":
            return pd.read_parquet(path)
        elif self.config.local_format == "csv":
            return pd.read_csv(path)
        elif self.config.local_format == "hdf5":
            return pd.read_hdf(path, key='data')
        elif self.config.local_format == "pickle":
            with open(path, 'rb') as f:
                return pickle.load(f)
        else:
            raise StorageError(f"Format local non supporté: {self.config.local_format}")
    
    async def _delete_local(self, name: str, version: Optional[int] = None) -> bool:
        """Supprime du stockage local."""
        data_id = self._generate_id(name)
        
        if version is not None:
            path = Path(self.config.local_path) / f"{data_id}_v{version}.{self.config.local_format}"
        else:
            path = Path(self.config.local_path) / f"{data_id}.{self.config.local_format}"
        
        if path.exists():
            path.unlink()
            return True
        
        return False
    
    # ============================================================
    # STOCKAGE POSTGRES
    # ============================================================
    
    async def _store_postgres(self, df: pd.DataFrame, name: str, data_id: str) -> str:
        """Stocke dans PostgreSQL."""
        if not POSTGRES_AVAILABLE:
            raise StorageError("PostgreSQL non disponible")
        
        engine = self._connections.get(StorageType.POSTGRES)
        if engine is None:
            await self._connect_postgres()
            engine = self._connections.get(StorageType.POSTGRES)
        
        table_name = f"{self.config.postgres_table_prefix}{data_id}"
        
        # Création de la table
        df.head(0).to_sql(table_name, engine, if_exists='replace', index=False)
        
        # Insertion par batch
        for i in range(0, len(df), self.config.batch_size):
            batch = df.iloc[i:i+self.config.batch_size]
            batch.to_sql(table_name, engine, if_exists='append', index=False)
        
        return table_name
    
    async def _load_postgres(self, name: str, version: Optional[int] = None) -> pd.DataFrame:
        """Charge depuis PostgreSQL."""
        if not POSTGRES_AVAILABLE:
            raise StorageError("PostgreSQL non disponible")
        
        engine = self._connections.get(StorageType.POSTGRES)
        if engine is None:
            await self._connect_postgres()
            engine = self._connections.get(StorageType.POSTGRES)
        
        data_id = self._generate_id(name)
        table_name = f"{self.config.postgres_table_prefix}{data_id}"
        
        query = f"SELECT * FROM {table_name}"
        if version is not None:
            query = f"SELECT * FROM {table_name}_v{version}"
        
        return pd.read_sql(query, engine)
    
    async def _delete_postgres(self, name: str, version: Optional[int] = None) -> bool:
        """Supprime de PostgreSQL."""
        if not POSTGRES_AVAILABLE:
            return False
        
        engine = self._connections.get(StorageType.POSTGRES)
        if engine is None:
            await self._connect_postgres()
            engine = self._connections.get(StorageType.POSTGRES)
        
        data_id = self._generate_id(name)
        table_name = f"{self.config.postgres_table_prefix}{data_id}"
        
        if version is not None:
            table_name = f"{table_name}_v{version}"
        
        with engine.connect() as conn:
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        return True
    
    # ============================================================
    # STOCKAGE MONGODB
    # ============================================================
    
    async def _store_mongodb(self, df: pd.DataFrame, name: str, data_id: str) -> str:
        """Stocke dans MongoDB."""
        if not MONGODB_AVAILABLE:
            raise StorageError("MongoDB non disponible")
        
        client = self._connections.get(StorageType.MONGODB)
        if client is None:
            await self._connect_mongodb()
            client = self._connections.get(StorageType.MONGODB)
        
        db = client[self.config.mongodb_database]
        collection_name = f"{self.config.mongodb_collection_prefix}{data_id}"
        collection = db[collection_name]
        
        # Conversion en dictionnaires
        records = df.to_dict('records')
        
        # Insertion par batch
        for i in range(0, len(records), self.config.batch_size):
            batch = records[i:i+self.config.batch_size]
            collection.insert_many(batch)
        
        return collection_name
    
    async def _load_mongodb(self, name: str, version: Optional[int] = None) -> pd.DataFrame:
        """Charge depuis MongoDB."""
        if not MONGODB_AVAILABLE:
            raise StorageError("MongoDB non disponible")
        
        client = self._connections.get(StorageType.MONGODB)
        if client is None:
            await self._connect_mongodb()
            client = self._connections.get(StorageType.MONGODB)
        
        db = client[self.config.mongodb_database]
        data_id = self._generate_id(name)
        collection_name = f"{self.config.mongodb_collection_prefix}{data_id}"
        collection = db[collection_name]
        
        records = list(collection.find({}, {'_id': 0}))
        return pd.DataFrame(records)
    
    async def _delete_mongodb(self, name: str, version: Optional[int] = None) -> bool:
        """Supprime de MongoDB."""
        if not MONGODB_AVAILABLE:
            return False
        
        client = self._connections.get(StorageType.MONGODB)
        if client is None:
            await self._connect_mongodb()
            client = self._connections.get(StorageType.MONGODB)
        
        db = client[self.config.mongodb_database]
        data_id = self._generate_id(name)
        collection_name = f"{self.config.mongodb_collection_prefix}{data_id}"
        collection = db[collection_name]
        
        collection.drop()
        return True
    
    # ============================================================
    # STOCKAGE REDIS
    # ============================================================
    
    async def _store_redis(self, df: pd.DataFrame, name: str, data_id: str) -> str:
        """Stocke dans Redis."""
        if not REDIS_AVAILABLE:
            raise StorageError("Redis non disponible")
        
        client = self._connections.get(StorageType.REDIS)
        if client is None:
            await self._connect_redis()
            client = self._connections.get(StorageType.REDIS)
        
        key = f"ai:{data_id}"
        
        # Compression et sérialisation
        data = df.to_json(orient='records')
        compressed = self._compress_data(data)
        
        client.setex(key, self.config.redis_ttl, compressed)
        return key
    
    async def _load_redis(self, name: str, version: Optional[int] = None) -> pd.DataFrame:
        """Charge depuis Redis."""
        if not REDIS_AVAILABLE:
            raise StorageError("Redis non disponible")
        
        client = self._connections.get(StorageType.REDIS)
        if client is None:
            await self._connect_redis()
            client = self._connections.get(StorageType.REDIS)
        
        data_id = self._generate_id(name)
        key = f"ai:{data_id}"
        
        data = client.get(key)
        if data is None:
            raise StorageError(f"Clé non trouvée: {key}")
        
        decompressed = self._decompress_data(data)
        return pd.read_json(decompressed, orient='records')
    
    async def _delete_redis(self, name: str, version: Optional[int] = None) -> bool:
        """Supprime de Redis."""
        if not REDIS_AVAILABLE:
            return False
        
        client = self._connections.get(StorageType.REDIS)
        if client is None:
            await self._connect_redis()
            client = self._connections.get(StorageType.REDIS)
        
        data_id = self._generate_id(name)
        key = f"ai:{data_id}"
        
        return client.delete(key) > 0
    
    # ============================================================
    # STOCKAGE CLOUD
    # ============================================================
    
    async def _store_cloud(self, df: pd.DataFrame, name: str, data_id: str) -> str:
        """Stocke dans le cloud."""
        data = df.to_parquet(compression=self.config.compression.value)
        
        if self.config.primary_storage == StorageType.S3:
            return await self._store_s3(data, data_id)
        elif self.config.primary_storage == StorageType.GCS:
            return await self._store_gcs(data, data_id)
        elif self.config.primary_storage == StorageType.AZURE:
            return await self._store_azure(data, data_id)
        else:
            raise StorageError(f"Cloud non supporté: {self.config.primary_storage}")
    
    async def _store_s3(self, data: bytes, data_id: str) -> str:
        """Stocke sur S3."""
        s3 = self._connections.get(StorageType.S3)
        if s3 is None:
            await self._connect_s3()
            s3 = self._connections.get(StorageType.S3)
        
        key = f"{self.config.s3_prefix}{data_id}.parquet"
        s3.put_object(
            Bucket=self.config.s3_bucket,
            Key=key,
            Body=data
        )
        return f"s3://{self.config.s3_bucket}/{key}"
    
    async def _store_gcs(self, data: bytes, data_id: str) -> str:
        """Stocke sur GCS."""
        client = self._connections.get(StorageType.GCS)
        if client is None:
            await self._connect_gcp()
            client = self._connections.get(StorageType.GCS)
        
        bucket = client.bucket(self.config.gcp_bucket)
        key = f"{self.config.gcp_prefix}{data_id}.parquet"
        blob = bucket.blob(key)
        blob.upload_from_string(data)
        return f"gs://{self.config.gcp_bucket}/{key}"
    
    async def _store_azure(self, data: bytes, data_id: str) -> str:
        """Stocke sur Azure."""
        client = self._connections.get(StorageType.AZURE)
        if client is None:
            await self._connect_azure()
            client = self._connections.get(StorageType.AZURE)
        
        container = client.get_container_client(self.config.azure_container)
        key = f"{self.config.azure_prefix}{data_id}.parquet"
        container.upload_blob(key, data)
        return f"azure://{self.config.azure_container}/{key}"
    
    async def _load_cloud(self, name: str, version: Optional[int] = None) -> pd.DataFrame:
        """Charge depuis le cloud."""
        data_id = self._generate_id(name)
        
        if self.config.primary_storage == StorageType.S3:
            data = await self._load_s3(data_id)
        elif self.config.primary_storage == StorageType.GCS:
            data = await self._load_gcs(data_id)
        elif self.config.primary_storage == StorageType.AZURE:
            data = await self._load_azure(data_id)
        else:
            raise StorageError(f"Cloud non supporté: {self.config.primary_storage}")
        
        return pd.read_parquet(data)
    
    async def _load_s3(self, data_id: str) -> bytes:
        """Charge depuis S3."""
        s3 = self._connections.get(StorageType.S3)
        if s3 is None:
            await self._connect_s3()
            s3 = self._connections.get(StorageType.S3)
        
        key = f"{self.config.s3_prefix}{data_id}.parquet"
        response = s3.get_object(Bucket=self.config.s3_bucket, Key=key)
        return response['Body'].read()
    
    async def _load_gcs(self, data_id: str) -> bytes:
        """Charge depuis GCS."""
        client = self._connections.get(StorageType.GCS)
        if client is None:
            await self._connect_gcp()
            client = self._connections.get(StorageType.GCS)
        
        bucket = client.bucket(self.config.gcp_bucket)
        key = f"{self.config.gcp_prefix}{data_id}.parquet"
        blob = bucket.blob(key)
        return blob.download_as_bytes()
    
    async def _load_azure(self, data_id: str) -> bytes:
        """Charge depuis Azure."""
        client = self._connections.get(StorageType.AZURE)
        if client is None:
            await self._connect_azure()
            client = self._connections.get(StorageType.AZURE)
        
        container = client.get_container_client(self.config.azure_container)
        key = f"{self.config.azure_prefix}{data_id}.parquet"
        blob = container.get_blob_client(key)
        return blob.download_blob().readall()
    
    async def _delete_cloud(self, name: str, version: Optional[int] = None) -> bool:
        """Supprime du cloud."""
        data_id = self._generate_id(name)
        
        if self.config.primary_storage == StorageType.S3:
            return await self._delete_s3(data_id)
        elif self.config.primary_storage == StorageType.GCS:
            return await self._delete_gcs(data_id)
        elif self.config.primary_storage == StorageType.AZURE:
            return await self._delete_azure(data_id)
        
        return False
    
    async def _delete_s3(self, data_id: str) -> bool:
        """Supprime de S3."""
        s3 = self._connections.get(StorageType.S3)
        if s3 is None:
            await self._connect_s3()
            s3 = self._connections.get(StorageType.S3)
        
        key = f"{self.config.s3_prefix}{data_id}.parquet"
        s3.delete_object(Bucket=self.config.s3_bucket, Key=key)
        return True
    
    async def _delete_gcs(self, data_id: str) -> bool:
        """Supprime de GCS."""
        client = self._connections.get(StorageType.GCS)
        if client is None:
            await self._connect_gcp()
            client = self._connections.get(StorageType.GCS)
        
        bucket = client.bucket(self.config.gcp_bucket)
        key = f"{self.config.gcp_prefix}{data_id}.parquet"
        blob = bucket.blob(key)
        blob.delete()
        return True
    
    async def _delete_azure(self, data_id: str) -> bool:
        """Supprime de Azure."""
        client = self._connections.get(StorageType.AZURE)
        if client is None:
            await self._connect_azure()
            client = self._connections.get(StorageType.AZURE)
        
        container = client.get_container_client(self.config.azure_container)
        key = f"{self.config.azure_prefix}{data_id}.parquet"
        container.delete_blob(key)
        return True
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def _to_dataframe(self, data: Union[pd.DataFrame, np.ndarray, Dict, List]) -> pd.DataFrame:
        """Convertit les données en DataFrame."""
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, np.ndarray):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            return pd.DataFrame([data])
        elif isinstance(data, list):
            if all(isinstance(x, dict) for x in data):
                return pd.DataFrame(data)
            return pd.DataFrame({col: [d[col] for d in data] for col in data[0].keys()})
        else:
            raise StorageError(f"Type de données non supporté: {type(data)}")
    
    def _generate_id(self, name: str) -> str:
        """Génère un ID unique pour un dataset."""
        timestamp = datetime.now().strftime(self.config.version_format)
        name_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        return f"{name}_{timestamp}_{name_hash}"
    
    def _calculate_hash(self, df: pd.DataFrame) -> str:
        """Calcule le hash d'un DataFrame."""
        return hashlib.md5(df.to_json().encode()).hexdigest()
    
    def _compress_data(self, data: Union[pd.DataFrame, str, bytes]) -> bytes:
        """Compresse les données."""
        if isinstance(data, pd.DataFrame):
            data = data.to_json().encode()
        elif isinstance(data, str):
            data = data.encode()
        
        if self.config.compression == CompressionType.GZIP:
            return gzip.compress(data, self.config.compression_level)
        elif self.config.compression == CompressionType.ZLIB:
            return zlib.compress(data, self.config.compression_level)
        else:
            return data
    
    def _decompress_data(self, data: bytes) -> bytes:
        """Décompresse les données."""
        if self.config.compression == CompressionType.GZIP:
            return gzip.decompress(data)
        elif self.config.compression == CompressionType.ZLIB:
            return zlib.decompress(data)
        else:
            return data
    
    def _get_next_version(self, name: str) -> int:
        """Retourne le prochain numéro de version."""
        data_id = self._generate_id(name)
        path = Path(self.config.local_path)
        existing = list(path.glob(f"{data_id}_v*.{self.config.local_format}"))
        if existing:
            versions = [int(f.stem.split('_v')[-1]) for f in existing]
            return max(versions) + 1
        return 1
    
    async def _copy_file(self, src: Path, dst: Path) -> None:
        """Copie un fichier."""
        import shutil
        shutil.copy2(src, dst)
    
    async def _save_metadata(self, metadata: StorageMetadata) -> None:
        """Sauvegarde les métadonnées."""
        self._metadata[metadata.id] = metadata
        
        # Sauvegarde persistante
        metadata_path = Path(self.config.local_path) / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(
                {k: v.to_dict() for k, v in self._metadata.items()},
                f,
                indent=2,
                default=str
            )
    
    async def get_metadata(self, name: str) -> Optional[StorageMetadata]:
        """
        Récupère les métadonnées d'un dataset.
        
        Args:
            name: Nom du dataset.
            
        Returns:
            Métadonnées ou None.
        """
        data_id = self._generate_id(name)
        return self._metadata.get(data_id)
    
    async def list_datasets(self) -> List[Dict[str, Any]]:
        """
        Liste tous les datasets disponibles.
        
        Returns:
            Liste des datasets.
        """
        datasets = []
        
        if self.config.primary_storage == StorageType.LOCAL:
            path = Path(self.config.local_path)
            for file in path.glob(f"*.{self.config.local_format}"):
                if '_v' not in file.stem:  # Ignorer les versions
                    datasets.append({
                        'name': file.stem,
                        'path': str(file),
                        'size': file.stat().st_size,
                        'modified': datetime.fromtimestamp(file.stat().st_mtime)
                    })
        
        # Ajouter les métadonnées
        for metadata in self._metadata.values():
            datasets.append(metadata.to_dict())
        
        return datasets
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du stockage.
        
        Returns:
            Statistiques.
        """
        return {
            'primary_storage': self.config.primary_storage.value,
            'is_connected': self._is_connected,
            'cache_size': len(self._cache),
            'metadata_count': len(self._metadata),
            'total_datasets': len(self._metadata)
        }


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_storage(
    storage_type: str = "local",
    **kwargs
) -> DataStorage:
    """
    Crée un gestionnaire de stockage avec configuration simplifiée.
    
    Args:
        storage_type: Type de stockage.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du DataStorage.
    """
    type_map = {
        'local': StorageType.LOCAL,
        'postgres': StorageType.POSTGRES,
        'timescale': StorageType.TIMESCALE,
        'mongodb': StorageType.MONGODB,
        'redis': StorageType.REDIS,
        's3': StorageType.S3,
        'gcs': StorageType.GCS,
        'azure': StorageType.AZURE
    }
    
    config = StorageConfig(
        primary_storage=type_map.get(storage_type, StorageType.LOCAL),
        **kwargs
    )
    return DataStorage(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'DataStorage',
    'StorageConfig',
    'StorageMetadata',
    'StorageType',
    'CompressionType',
    'create_storage'
]

# ============================================================
# FIN DU FICHIER
# ============================================================
