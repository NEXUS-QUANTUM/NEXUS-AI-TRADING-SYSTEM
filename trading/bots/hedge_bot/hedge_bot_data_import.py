# trading/bots/hedge_bot/hedge_bot_data_import.py
# Advanced Data Import & Ingestion Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Import Module - Module avancé d'importation et d'ingestion de données pour le Hedge Bot.
Gère l'importation de données depuis diverses sources, la validation, la transformation,
le mapping et l'intégration des données dans le système de hedging.
"""

import asyncio
import json
import csv
import io
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib
import re
import aiohttp
import aiohttp.client_exceptions
from pathlib import Path
import mimetypes
import tempfile
import zipfile
import gzip
import shutil

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_import")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)
from trading.bots.hedge_bot.hedge_bot_data_validation import (
    ValidationEngine, ValidationResult
)


# ============== ENUMS & TYPES ==============

class ImportSourceType(Enum):
    """Types de sources d'importation."""
    LOCAL_FILE = "local_file"
    URL = "url"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    FTP = "ftp"
    SFTP = "sftp"
    DATABASE = "database"
    API = "api"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    WEBSOCKET = "websocket"
    EMAIL = "email"
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"


class ImportFormat(Enum):
    """Formats d'importation."""
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"
    PARQUET = "parquet"
    EXCEL = "excel"
    XML = "xml"
    HTML = "html"
    PDF = "pdf"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PROTOBUF = "protobuf"
    ARROW = "arrow"
    ORC = "orc"
    AVRO = "avro"
    HDF5 = "hdf5"
    SQL = "sql"


class ImportMode(Enum):
    """Modes d'importation."""
    OVERWRITE = "overwrite"          # Écraser
    APPEND = "append"                # Ajouter
    UPSERT = "upsert"                # Mettre à jour ou insérer
    REPLACE = "replace"              # Remplacer partiellement
    MERGE = "merge"                  # Fusionner
    INCREMENTAL = "incremental"      # Incrémental
    FULL = "full"                    # Complet


class ImportStatus(Enum):
    """Statuts d'importation."""
    PENDING = "pending"              # En attente
    VALIDATING = "validating"        # En validation
    PROCESSING = "processing"        # En traitement
    COMPLETED = "completed"          # Terminé
    FAILED = "failed"                # Échoué
    CANCELLED = "cancelled"          # Annulé
    PARTIAL = "partial"              # Partiel


# ============== DATA MODELS ==============

@dataclass
class ImportJob:
    """Job d'importation."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source_type: ImportSourceType = ImportSourceType.LOCAL_FILE
    source_path: str = ""
    source_config: Dict[str, Any] = field(default_factory=dict)
    import_format: ImportFormat = ImportFormat.CSV
    import_mode: ImportMode = ImportMode.APPEND
    target_data_type: DataType = DataType.MARKET
    target_path: str = ""
    mapping: Dict[str, str] = field(default_factory=dict)
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    validate: bool = True
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    batch_size: int = 10000
    max_rows: Optional[int] = None
    skip_rows: int = 0
    encoding: str = "utf-8"
    compress: bool = False
    status: ImportStatus = ImportStatus.PENDING
    total_rows: int = 0
    processed_rows: int = 0
    error_rows: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    progress: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "source_type": self.source_type.value,
            "source_path": self.source_path,
            "source_config": self.source_config,
            "import_format": self.import_format.value,
            "import_mode": self.import_mode.value,
            "target_data_type": self.target_data_type.value,
            "target_path": self.target_path,
            "mapping": self.mapping,
            "transformations": self.transformations,
            "filters": self.filters,
            "validate": self.validate,
            "validation_rules": self.validation_rules,
            "batch_size": self.batch_size,
            "max_rows": self.max_rows,
            "skip_rows": self.skip_rows,
            "encoding": self.encoding,
            "compress": self.compress,
            "status": self.status.value,
            "total_rows": self.total_rows,
            "processed_rows": self.processed_rows,
            "error_rows": self.error_rows,
            "errors": self.errors,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "metadata": self.metadata,
            "tags": self.tags,
            "progress": self.progress
        }


@dataclass
class ImportResult:
    """Résultat d'importation."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    success: bool = False
    rows_imported: int = 0
    rows_failed: int = 0
    rows_skipped: int = 0
    validation_results: List[ValidationResult] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class ImportEngineInterface(ABC):
    """Interface abstraite pour le moteur d'importation."""
    
    @abstractmethod
    async def create_job(self, config: Dict[str, Any]) -> ImportJob:
        """Crée un job d'importation."""
        pass
    
    @abstractmethod
    async def run_job(self, job_id: str) -> ImportResult:
        """Exécute un job d'importation."""
        pass
    
    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[ImportJob]:
        """Récupère un job d'importation."""
        pass


# ============== IMPLÉMENTATION ==============

class ImportEngine(ImportEngineInterface):
    """
    Moteur d'importation de données avancé pour le Hedge Bot.
    Gère l'ingestion de données depuis diverses sources avec validation et transformation.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        validation_engine: Optional[ValidationEngine] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.validation_engine = validation_engine
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des jobs
        self._jobs: Dict[str, ImportJob] = {}
        self._jobs_lock = threading.RLock()
        
        # Gestion des résultats
        self._results: Dict[str, ImportResult] = {}
        self._results_lock = threading.RLock()
        
        # Cache des fichiers
        self._file_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "jobs_created": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "rows_imported": 0,
            "rows_failed": 0,
            "total_duration_ms": 0.0,
            "avg_job_duration_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Queue d'importation
        self._import_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        # État
        self._is_running = False
        
        logger.info("ImportEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_batch_size": 10000,
            "max_file_size": 1024 * 1024 * 1024,  # 1 GB
            "timeout": 3600,
            "retry_count": 3,
            "retry_delay": 1.0,
            "cache_size": 1000,
            "enable_cache": True,
            "default_encoding": "utf-8",
            "temp_dir": "/tmp/nexus_import",
            "chunk_size": 8192,
            "max_concurrent_jobs": 3
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'importation."""
        logger.info("ImportEngine starting...")
        self._is_running = True
        
        # Création du dossier temporaire
        Path(self.config["temp_dir"]).mkdir(parents=True, exist_ok=True)
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config["timeout"])
        )
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._import_processor())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("ImportEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'importation."""
        logger.info("ImportEngine stopping...")
        self._is_running = False
        
        # Drain de la queue
        await self._drain_queue()
        
        # Fermeture de la session
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("ImportEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_job(self, config: Dict[str, Any]) -> ImportJob:
        """Crée un job d'importation."""
        job = ImportJob(
            name=config.get("name", f"Import_{uuid.uuid4().hex[:8]}"),
            source_type=ImportSourceType(config.get("source_type", "local_file")),
            source_path=config.get("source_path", ""),
            source_config=config.get("source_config", {}),
            import_format=ImportFormat(config.get("import_format", "csv")),
            import_mode=ImportMode(config.get("import_mode", "append")),
            target_data_type=DataType(config.get("target_data_type", "market")),
            target_path=config.get("target_path", ""),
            mapping=config.get("mapping", {}),
            transformations=config.get("transformations", []),
            filters=config.get("filters", {}),
            validate=config.get("validate", True),
            validation_rules=config.get("validation_rules", {}),
            batch_size=config.get("batch_size", self.config["default_batch_size"]),
            max_rows=config.get("max_rows"),
            skip_rows=config.get("skip_rows", 0),
            encoding=config.get("encoding", self.config["default_encoding"]),
            compress=config.get("compress", False),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        with self._jobs_lock:
            self._jobs[job.job_id] = job
            self._stats["jobs_created"] += 1
        
        # Mise en queue
        await self._import_queue.put(job)
        
        logger.info(f"Import job created: {job.name} (id={job.job_id})")
        return job
    
    async def run_job(self, job_id: str) -> ImportResult:
        """Exécute un job d'importation."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
        
        start_time = time.time()
        job.start_time = datetime.now(timezone.utc)
        job.status = ImportStatus.PROCESSING
        
        try:
            # 1. Lecture des données
            data = await self._read_data(job)
            
            # 2. Validation
            if job.validate:
                validation_result = await self._validate_data(job, data)
                if not validation_result.success:
                    job.status = ImportStatus.FAILED
                    job.errors.append(f"Validation failed: {validation_result.message}")
                    return await self._create_result(job, success=False, error=validation_result.message)
            
            # 3. Transformation
            transformed_data = await self._transform_data(job, data)
            
            # 4. Mapping
            mapped_data = await self._map_data(job, transformed_data)
            
            # 5. Filtrage
            filtered_data = await self._filter_data(job, mapped_data)
            
            # 6. Importation
            result = await self._import_data(job, filtered_data)
            
            # Mise à jour du job
            job.status = ImportStatus.COMPLETED if result.success else ImportStatus.FAILED
            job.processed_rows = result.rows_imported
            job.error_rows = result.rows_failed
            job.progress = 1.0
            job.end_time = datetime.now(timezone.utc)
            
            self._stats["jobs_completed"] += 1
            self._stats["rows_imported"] += result.rows_imported
            self._stats["rows_failed"] += result.rows_failed
            
            logger.info(f"Import job completed: {job.name} rows={result.rows_imported}")
            
            return result
            
        except Exception as e:
            job.status = ImportStatus.FAILED
            job.errors.append(str(e))
            job.end_time = datetime.now(timezone.utc)
            self._stats["jobs_failed"] += 1
            
            logger.error(f"Import job failed: {job.name} - {e}")
            return await self._create_result(job, success=False, error=str(e))
    
    async def get_job(self, job_id: str) -> Optional[ImportJob]:
        """Récupère un job d'importation."""
        with self._jobs_lock:
            return self._jobs.get(job_id)
    
    async def get_jobs(self, status: Optional[ImportStatus] = None) -> List[ImportJob]:
        """Récupère les jobs d'importation."""
        with self._jobs_lock:
            jobs = list(self._jobs.values())
            if status:
                jobs = [j for j in jobs if j.status == status]
            return sorted(jobs, key=lambda j: j.start_time or j.job_id, reverse=True)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Annule un job d'importation."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job or job.status in [ImportStatus.COMPLETED, ImportStatus.FAILED, ImportStatus.CANCELLED]:
                return False
            
            job.status = ImportStatus.CANCELLED
            job.end_time = datetime.now(timezone.utc)
            return True
    
    # ========== MÉTHODES PRIVÉES - LECTURE ==========
    
    async def _read_data(self, job: ImportJob) -> Any:
        """Lit les données depuis la source."""
        if job.source_type == ImportSourceType.LOCAL_FILE:
            return await self._read_local_file(job)
        elif job.source_type == ImportSourceType.URL:
            return await self._read_url(job)
        elif job.source_type in [ImportSourceType.S3, ImportSourceType.GCS, ImportSourceType.AZURE]:
            return await self._read_cloud_file(job)
        elif job.source_type in [ImportSourceType.FTP, ImportSourceType.SFTP]:
            return await self._read_ftp(job)
        elif job.source_type == ImportSourceType.API:
            return await self._read_api(job)
        else:
            raise ValueError(f"Unsupported source type: {job.source_type}")
    
    async def _read_local_file(self, job: ImportJob) -> Any:
        """Lit un fichier local."""
        file_path = Path(job.source_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {job.source_path}")
        
        # Vérification de la taille
        file_size = file_path.stat().st_size
        if file_size > self.config["max_file_size"]:
            raise ValueError(f"File too large: {file_size} > {self.config['max_file_size']}")
        
        # Lecture selon le format
        if job.import_format == ImportFormat.CSV:
            return await self._read_csv(file_path, job)
        elif job.import_format == ImportFormat.JSON:
            return await self._read_json(file_path, job)
        elif job.import_format == ImportFormat.JSONL:
            return await self._read_jsonl(file_path, job)
        elif job.import_format == ImportFormat.PARQUET:
            return await self._read_parquet(file_path, job)
        elif job.import_format == ImportFormat.EXCEL:
            return await self._read_excel(file_path, job)
        else:
            raise ValueError(f"Unsupported import format: {job.import_format}")
    
    async def _read_csv(self, file_path: Path, job: ImportJob) -> pd.DataFrame:
        """Lit un fichier CSV."""
        try:
            # Détection du séparateur
            sep = self._detect_separator(file_path)
            
            # Lecture
            df = pd.read_csv(
                file_path,
                sep=sep,
                encoding=job.encoding,
                skiprows=job.skip_rows,
                nrows=job.max_rows,
                dtype=str,
                na_values=['', 'NA', 'null', 'NULL', 'None']
            )
            
            return df
            
        except Exception as e:
            logger.error(f"CSV read error: {e}")
            raise
    
    async def _read_json(self, file_path: Path, job: ImportJob) -> pd.DataFrame:
        """Lit un fichier JSON."""
        try:
            with open(file_path, 'r', encoding=job.encoding) as f:
                data = json.load(f)
            
            # Conversion en DataFrame
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                raise ValueError(f"Unsupported JSON structure: {type(data)}")
            
            # Limitation du nombre de lignes
            if job.max_rows:
                df = df.head(job.max_rows)
            
            return df
            
        except Exception as e:
            logger.error(f"JSON read error: {e}")
            raise
    
    async def _read_jsonl(self, file_path: Path, job: ImportJob) -> pd.DataFrame:
        """Lit un fichier JSONL."""
        data = []
        
        try:
            with open(file_path, 'r', encoding=job.encoding) as f:
                for i, line in enumerate(f):
                    if i < job.skip_rows:
                        continue
                    if job.max_rows and len(data) >= job.max_rows:
                        break
                    if line.strip():
                        data.append(json.loads(line.strip()))
            
            return pd.DataFrame(data)
            
        except Exception as e:
            logger.error(f"JSONL read error: {e}")
            raise
    
    async def _read_parquet(self, file_path: Path, job: ImportJob) -> pd.DataFrame:
        """Lit un fichier Parquet."""
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(str(file_path))
            df = table.to_pandas()
            
            if job.max_rows:
                df = df.head(job.max_rows)
            
            return df
            
        except ImportError:
            logger.warning("PyArrow not available, falling back to CSV")
            return await self._read_csv(file_path, job)
    
    async def _read_excel(self, file_path: Path, job: ImportJob) -> pd.DataFrame:
        """Lit un fichier Excel."""
        try:
            # Lecture de la première feuille
            df = pd.read_excel(
                file_path,
                skiprows=job.skip_rows,
                nrows=job.max_rows,
                dtype=str
            )
            
            return df
            
        except Exception as e:
            logger.error(f"Excel read error: {e}")
            raise
    
    async def _read_url(self, job: ImportJob) -> pd.DataFrame:
        """Lit des données depuis une URL."""
        if not self._session:
            raise RuntimeError("HTTP session not initialized")
        
        try:
            async with self._session.get(job.source_path) as response:
                if response.status != 200:
                    raise Exception(f"HTTP error: {response.status}")
                
                content = await response.read()
                
                # Sauvegarde temporaire
                temp_path = Path(self.config["temp_dir"]) / f"{uuid.uuid4()}.tmp"
                with open(temp_path, 'wb') as f:
                    f.write(content)
                
                # Lecture selon le format
                job.source_path = str(temp_path)
                result = await self._read_local_file(job)
                
                # Nettoyage
                temp_path.unlink()
                
                return result
                
        except Exception as e:
            logger.error(f"URL read error: {e}")
            raise
    
    async def _read_cloud_file(self, job: ImportJob) -> pd.DataFrame:
        """Lit un fichier cloud."""
        # Implémentation spécifique au cloud provider
        raise NotImplementedError("Cloud file reading not implemented yet")
    
    async def _read_ftp(self, job: ImportJob) -> pd.DataFrame:
        """Lit un fichier FTP/SFTP."""
        # Implémentation spécifique au FTP
        raise NotImplementedError("FTP reading not implemented yet")
    
    async def _read_api(self, job: ImportJob) -> pd.DataFrame:
        """Lit des données depuis une API."""
        # Implémentation spécifique à l'API
        raise NotImplementedError("API reading not implemented yet")
    
    def _detect_separator(self, file_path: Path) -> str:
        """Détecte le séparateur d'un fichier CSV."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
            
            # Détection des séparateurs courants
            separators = [',', ';', '\t', '|']
            for sep in separators:
                if first_line.count(sep) > 1:
                    return sep
            
            return ','
            
        except:
            return ','
    
    # ========== MÉTHODES PRIVÉES - VALIDATION ==========
    
    async def _validate_data(self, job: ImportJob, data: Any) -> ValidationResult:
        """Valide les données importées."""
        if not self.validation_engine:
            return ValidationResult(success=True, message="No validation engine")
        
        # Validation selon les règles
        result = await self.validation_engine.validate(
            data,
            job.validation_rules,
            job.target_data_type
        )
        
        return result
    
    # ========== MÉTHODES PRIVÉES - TRANSFORMATION ==========
    
    async def _transform_data(self, job: ImportJob, data: pd.DataFrame) -> pd.DataFrame:
        """Transforme les données selon les règles."""
        if not job.transformations:
            return data
        
        result = data.copy()
        
        for transform in job.transformations:
            transform_type = transform.get("type")
            
            if transform_type == "normalize":
                # Normalisation des colonnes
                columns = transform.get("columns", [])
                method = transform.get("method", "zscore")
                
                for col in columns:
                    if col in result.columns:
                        if method == "zscore":
                            mean = result[col].mean()
                            std = result[col].std()
                            if std > 0:
                                result[col] = (result[col] - mean) / std
                        elif method == "minmax":
                            min_val = result[col].min()
                            max_val = result[col].max()
                            if max_val != min_val:
                                result[col] = (result[col] - min_val) / (max_val - min_val)
            
            elif transform_type == "clean_text":
                # Nettoyage de texte
                columns = transform.get("columns", [])
                
                for col in columns:
                    if col in result.columns:
                        result[col] = result[col].astype(str).str.strip()
                        result[col] = result[col].str.replace(r'\s+', ' ', regex=True)
            
            elif transform_type == "convert":
                # Conversion de type
                mapping = transform.get("mapping", {})
                
                for col, dtype in mapping.items():
                    if col in result.columns:
                        try:
                            result[col] = result[col].astype(dtype)
                        except:
                            pass
            
            elif transform_type == "date_parse":
                # Parsing de dates
                columns = transform.get("columns", [])
                format = transform.get("format", "ISO8601")
                
                for col in columns:
                    if col in result.columns:
                        try:
                            if format == "ISO8601":
                                result[col] = pd.to_datetime(result[col])
                            else:
                                result[col] = pd.to_datetime(result[col], format=format)
                        except:
                            pass
        
        return result
    
    # ========== MÉTHODES PRIVÉES - MAPPING ==========
    
    async def _map_data(self, job: ImportJob, data: pd.DataFrame) -> pd.DataFrame:
        """Applique le mapping des colonnes."""
        if not job.mapping:
            return data
        
        result = data.copy()
        
        # Renommage des colonnes
        result.rename(columns=job.mapping, inplace=True)
        
        # Suppression des colonnes non mappées
        keep_cols = list(job.mapping.values())
        result = result[[col for col in result.columns if col in keep_cols or col in data.columns]]
        
        return result
    
    # ========== MÉTHODES PRIVÉES - FILTRAGE ==========
    
    async def _filter_data(self, job: ImportJob, data: pd.DataFrame) -> pd.DataFrame:
        """Applique les filtres."""
        if not job.filters:
            return data
        
        result = data.copy()
        
        for key, value in job.filters.items():
            if key in result.columns:
                if isinstance(value, (list, tuple)):
                    result = result[result[key].isin(value)]
                elif isinstance(value, dict):
                    operator = value.get("operator", "eq")
                    val = value.get("value")
                    
                    if operator == "eq":
                        result = result[result[key] == val]
                    elif operator == "ne":
                        result = result[result[key] != val]
                    elif operator == "gt":
                        result = result[result[key] > val]
                    elif operator == "gte":
                        result = result[result[key] >= val]
                    elif operator == "lt":
                        result = result[result[key] < val]
                    elif operator == "lte":
                        result = result[result[key] <= val]
                    elif operator == "contains":
                        result = result[result[key].str.contains(val, na=False)]
                    elif operator == "regex":
                        result = result[result[key].str.match(val, na=False)]
                else:
                    result = result[result[key] == value]
        
        return result
    
    # ========== MÉTHODES PRIVÉES - IMPORTATION ==========
    
    async def _import_data(self, job: ImportJob, data: pd.DataFrame) -> ImportResult:
        """Importe les données dans le système."""
        start_time = time.time()
        
        try:
            # Vérification du mode
            if job.import_mode == ImportMode.OVERWRITE:
                # Suppression des données existantes
                if self.data_manager:
                    await self._delete_existing_data(job)
            
            # Importation en batches
            total_rows = len(data)
            rows_imported = 0
            rows_failed = 0
            errors = []
            
            for i in range(0, total_rows, job.batch_size):
                batch = data.iloc[i:i+job.batch_size]
                
                try:
                    # Conversion en records
                    records = batch.to_dict('records')
                    
                    # Stockage
                    if self.data_manager:
                        for record in records:
                            # Conversion des types
                            record = self._convert_types(record)
                            
                            # Stockage
                            await self.data_manager.store(
                                f"{job.target_data_type.value}:{record.get('id', str(uuid.uuid4()))}",
                                record,
                                job.target_data_type
                            )
                    
                    rows_imported += len(records)
                    
                except Exception as e:
                    rows_failed += len(batch)
                    errors.append(f"Batch {i//job.batch_size}: {str(e)}")
            
            # Création du résultat
            result = ImportResult(
                job_id=job.job_id,
                success=rows_failed == 0,
                rows_imported=rows_imported,
                rows_failed=rows_failed,
                rows_skipped=total_rows - rows_imported - rows_failed,
                duration_ms=(time.time() - start_time) * 1000,
                error="; ".join(errors) if errors else None
            )
            
            # Stockage du résultat
            with self._results_lock:
                self._results[result.result_id] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Import error: {e}")
            return await self._create_result(job, success=False, error=str(e))
    
    def _convert_types(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Convertit les types pour le stockage."""
        result = {}
        
        for key, value in record.items():
            if isinstance(value, pd.Timestamp):
                result[key] = value.isoformat()
            elif isinstance(value, (np.integer, np.floating)):
                result[key] = float(value) if isinstance(value, np.floating) else int(value)
            elif isinstance(value, np.bool_):
                result[key] = bool(value)
            elif isinstance(value, (pd.Series, pd.DataFrame)):
                result[key] = value.tolist()
            else:
                result[key] = value
        
        return result
    
    async def _delete_existing_data(self, job: ImportJob) -> None:
        """Supprime les données existantes."""
        if self.data_manager:
            # Suppression en batch
            # Dans un système réel, on utiliserait une requête plus sophistiquée
            pass
    
    async def _create_result(self, job: ImportJob, success: bool, error: Optional[str] = None) -> ImportResult:
        """Crée un résultat d'importation."""
        result = ImportResult(
            job_id=job.job_id,
            success=success,
            error=error
        )
        
        with self._results_lock:
            self._results[result.result_id] = result
        
        return result
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _import_processor(self) -> None:
        """Traite les jobs d'importation."""
        while self._is_running:
            try:
                # Limitation du nombre de jobs concurrents
                with self._jobs_lock:
                    running = len([
                        j for j in self._jobs.values()
                        if j.status == ImportStatus.PROCESSING
                    ])
                
                if running >= self.config["max_concurrent_jobs"]:
                    await asyncio.sleep(1)
                    continue
                
                # Récupération du job
                try:
                    job = await asyncio.wait_for(
                        self._import_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Exécution du job
                asyncio.create_task(self.run_job(job.job_id))
                
            except Exception as e:
                logger.error(f"Import processor error: {e}")
                await asyncio.sleep(1)
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._file_cache) > self.config["cache_size"]:
                        keys = list(self._file_cache.keys())
                        for key in keys[:len(self._file_cache) - self.config["cache_size"]]:
                            del self._file_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._jobs_lock:
                    self._stats["pending_jobs"] = len([
                        j for j in self._jobs.values()
                        if j.status == ImportStatus.PENDING
                    ])
                    self._stats["processing_jobs"] = len([
                        j for j in self._jobs.values()
                        if j.status == ImportStatus.PROCESSING
                    ])
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "import:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _drain_queue(self) -> None:
        """Vide la queue d'importation."""
        while not self._import_queue.empty():
            try:
                job = await self._import_queue.get()
                job.status = ImportStatus.CANCELLED
                job.end_time = datetime.now(timezone.utc)
            except Exception:
                break
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_result(self, result_id: str) -> Optional[ImportResult]:
        """Récupère un résultat d'importation."""
        with self._results_lock:
            return self._results.get(result_id)
    
    async def get_results(self, job_id: str) -> List[ImportResult]:
        """Récupère les résultats d'un job."""
        with self._results_lock:
            return [r for r in self._results.values() if r.job_id == job_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._jobs_lock:
            self._stats["total_jobs"] = len(self._jobs)
        with self._results_lock:
            self._stats["total_results"] = len(self._results)
        
        return self._stats.copy()


# ============== IMPORT SCHEDULER ==============

class ImportScheduler:
    """
    Planificateur d'importations.
    Gère les importations programmées et récurrentes.
    """
    
    def __init__(self, engine: ImportEngine):
        self.engine = engine
        self._schedules: Dict[str, Dict[str, Any]] = {}
        self._schedule_lock = threading.RLock()
        self._is_running = False
        
        logger.info("ImportScheduler initialized")
    
    async def start(self) -> None:
        """Démarre le planificateur."""
        self._is_running = True
        asyncio.create_task(self._scheduler_loop())
        logger.info("ImportScheduler started")
    
    async def stop(self) -> None:
        """Arrête le planificateur."""
        self._is_running = False
        logger.info("ImportScheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Boucle de planification."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                now = datetime.now(timezone.utc)
                
                with self._schedule_lock:
                    for schedule_id, schedule in self._schedules.items():
                        if schedule.get("active", True):
                            if self._should_run(now, schedule):
                                # Création du job
                                job_config = schedule.get("job_config", {})
                                job = await self.engine.create_job(job_config)
                                
                                # Exécution du job
                                asyncio.create_task(self.engine.run_job(job.job_id))
                                
                                # Mise à jour de la dernière exécution
                                schedule["last_run"] = now
                
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
    
    def _should_run(self, now: datetime, schedule: Dict[str, Any]) -> bool:
        """Vérifie si l'importation doit être exécutée."""
        schedule_type = schedule.get("type", "daily")
        
        if schedule_type == "daily":
            hour = schedule.get("hour", 2)
            minute = schedule.get("minute", 0)
            return now.hour == hour and now.minute == minute
        
        elif schedule_type == "weekly":
            day = schedule.get("day", 0)
            hour = schedule.get("hour", 2)
            minute = schedule.get("minute", 0)
            return now.weekday() == day and now.hour == hour and now.minute == minute
        
        elif schedule_type == "interval":
            interval = schedule.get("interval", 3600)
            last_run = schedule.get("last_run")
            if not last_run:
                return True
            return (now - last_run).total_seconds() >= interval
        
        return False


# ============== FACTORY ==============

class ImportFactory:
    """Factory pour créer des composants d'importation."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        validation_engine: Optional[ValidationEngine] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ImportEngine:
        """Crée un moteur d'importation."""
        engine = ImportEngine(
            data_manager=data_manager,
            validation_engine=validation_engine,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    async def create_scheduler(engine: ImportEngine) -> ImportScheduler:
        """Crée un planificateur d'importations."""
        scheduler = ImportScheduler(engine)
        await scheduler.start()
        return scheduler


# ============== EXPORT ==============

__all__ = [
    "ImportSourceType",
    "ImportFormat",
    "ImportMode",
    "ImportStatus",
    "ImportJob",
    "ImportResult",
    "ImportEngineInterface",
    "ImportEngine",
    "ImportScheduler",
    "ImportFactory"
]
