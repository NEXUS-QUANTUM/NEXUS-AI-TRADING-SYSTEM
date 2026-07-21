"""
NEXUS AI TRADING SYSTEM - HEDGE BOT FILE UTILS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'utilitaires pour la gestion des fichiers du Hedge Bot.
Support des formats CSV, JSON, Parquet, Excel, et plus encore.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import csv
import gzip
import hashlib
import json
import logging
import os
import pickle
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, IO
from uuid import UUID, uuid4

import aiofiles
import numpy as np
import pandas as pd
import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class FileFormat(Enum):
    """Formats de fichiers supportés."""
    CSV = "csv"
    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    PARQUET = "parquet"
    EXCEL = "xlsx"
    HDF5 = "h5"
    PICKLE = "pkl"
    GZIP = "gz"
    ZIP = "zip"
    FEATHER = "feather"
    ORC = "orc"
    ARROW = "arrow"


class CompressionType(Enum):
    """Types de compression."""
    NONE = "none"
    GZIP = "gzip"
    ZIP = "zip"
    LZ4 = "lz4"
    SNAPPY = "snappy"
    ZSTD = "zstd"


@dataclass
class FileInfo:
    """Informations sur un fichier."""
    path: Path
    name: str
    extension: str
    size_bytes: int
    size_mb: float
    size_gb: float
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    is_compressed: bool
    compression_type: Optional[CompressionType]
    checksum: Optional[str]
    format: Optional[FileFormat]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "path": str(self.path),
            "name": self.name,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "size_mb": self.size_mb,
            "size_gb": self.size_gb,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "is_compressed": self.is_compressed,
            "compression_type": self.compression_type.value if self.compression_type else None,
            "checksum": self.checksum,
            "format": self.format.value if self.format else None,
            "metadata": self.metadata
        }


@dataclass
class FileMetadata:
    """Métadonnées de fichier."""
    file_id: UUID
    original_path: Path
    current_path: Path
    format: FileFormat
    compression: CompressionType
    encoding: str = "utf-8"
    schema: Dict[str, Any] = field(default_factory=dict)
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    size_bytes: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "file_id": str(self.file_id),
            "original_path": str(self.original_path),
            "current_path": str(self.current_path),
            "format": self.format.value,
            "compression": self.compression.value,
            "encoding": self.encoding,
            "schema": self.schema,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE FILE UTILS
# ============================================================================

class FileUtils:
    """
    Utilitaires pour la gestion des fichiers.
    Support des formats CSV, JSON, Parquet, Excel, etc.
    """

    # Taille des blocs pour la lecture/écriture
    CHUNK_SIZE = 1024 * 1024  # 1 MB

    # Formats supportés par extension
    EXTENSION_MAP = {
        ".csv": FileFormat.CSV,
        ".json": FileFormat.JSON,
        ".yaml": FileFormat.YAML,
        ".yml": FileFormat.YAML,
        ".xml": FileFormat.XML,
        ".parquet": FileFormat.PARQUET,
        ".xlsx": FileFormat.EXCEL,
        ".xls": FileFormat.EXCEL,
        ".h5": FileFormat.HDF5,
        ".hdf5": FileFormat.HDF5,
        ".pkl": FileFormat.PICKLE,
        ".pickle": FileFormat.PICKLE,
        ".gz": FileFormat.GZIP,
        ".zip": FileFormat.ZIP,
        ".feather": FileFormat.FEATHER,
        ".orc": FileFormat.ORC,
        ".arrow": FileFormat.ARROW
    }

    # Formats de compression
    COMPRESSION_EXTENSIONS = {
        ".gz": CompressionType.GZIP,
        ".zip": CompressionType.ZIP,
        ".lz4": CompressionType.LZ4,
        ".snappy": CompressionType.SNAPPY,
        ".zstd": CompressionType.ZSTD
    }

    def __init__(
        self,
        base_directory: Optional[str] = None,
        create_dirs: bool = True,
        max_file_size: int = 100 * 1024 * 1024  # 100 MB
    ):
        """
        Initialise les utilitaires de fichiers.

        Args:
            base_directory: Répertoire de base
            create_dirs: Créer les répertoires
            max_file_size: Taille maximale des fichiers
        """
        self.base_directory = Path(base_directory) if base_directory else Path.cwd() / "data"
        self.max_file_size = max_file_size
        
        # Création du répertoire de base
        if create_dirs:
            self.base_directory.mkdir(parents=True, exist_ok=True)
        
        # Sous-répertoires
        self.subdirs = {
            "raw": self.base_directory / "raw",
            "processed": self.base_directory / "processed",
            "backup": self.base_directory / "backup",
            "archive": self.base_directory / "archive",
            "temp": self.base_directory / "temp",
            "logs": self.base_directory / "logs"
        }
        
        # Création des sous-répertoires
        if create_dirs:
            for subdir in self.subdirs.values():
                subdir.mkdir(parents=True, exist_ok=True)
        
        # Cache des métadonnées
        self._metadata_cache: Dict[Path, FileMetadata] = {}
        self._file_info_cache: Dict[Path, FileInfo] = {}
        
        # Métriques
        self._metrics = {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_format": {},
            "by_compression": {},
            "last_operation": None
        }

        logger.info(f"FileUtils initialisé avec base_directory: {self.base_directory}")

    # ========================================================================
    # MÉTHODES DE LECTURE
    # ========================================================================

    async def read_file(
        self,
        file_path: Union[str, Path],
        format: Optional[FileFormat] = None,
        compression: Optional[CompressionType] = None,
        **kwargs
    ) -> Any:
        """
        Lit un fichier.

        Args:
            file_path: Chemin du fichier
            format: Format du fichier (optionnel)
            compression: Type de compression (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            Contenu du fichier
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileNotFoundError(f"Fichier non trouvé: {path}")

            # Détection automatique du format
            if not format:
                format = self._detect_format(path)
            
            # Détection de la compression
            if not compression:
                compression = self._detect_compression(path)

            # Lecture selon le format
            if format == FileFormat.CSV:
                return await self._read_csv(path, compression, **kwargs)
            elif format == FileFormat.JSON:
                return await self._read_json(path, compression, **kwargs)
            elif format == FileFormat.YAML:
                return await self._read_yaml(path, compression, **kwargs)
            elif format == FileFormat.XML:
                return await self._read_xml(path, compression, **kwargs)
            elif format == FileFormat.PARQUET:
                return await self._read_parquet(path, compression, **kwargs)
            elif format == FileFormat.EXCEL:
                return await self._read_excel(path, compression, **kwargs)
            elif format == FileFormat.PICKLE:
                return await self._read_pickle(path, compression, **kwargs)
            elif format == FileFormat.HDF5:
                return await self._read_hdf5(path, compression, **kwargs)
            elif format == FileFormat.FEATHER:
                return await self._read_feather(path, compression, **kwargs)
            else:
                raise ValueError(f"Format non supporté: {format}")

        except Exception as e:
            logger.error(f"Erreur lors de la lecture du fichier {file_path}: {e}")
            raise

    async def _read_csv(
        self,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> pd.DataFrame:
        """
        Lit un fichier CSV.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas

        Returns:
            DataFrame
        """
        try:
            file_obj = await self._open_file(path, compression)
            
            # Lecture avec pandas
            df = pd.read_csv(
                file_obj,
                **kwargs
            )
            
            # Mise à jour des métriques
            self._update_metrics(path, FileFormat.CSV, compression, len(df))
            
            return df

        except Exception as e:
            logger.error(f"Erreur lors de la lecture CSV: {e}")
            raise

    async def _read_json(
        self,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> Any:
        """
        Lit un fichier JSON.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments json

        Returns:
            Données JSON
        """
        try:
            file_obj = await self._open_file(path, compression)
            content = await file_obj.read()
            
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            data = json.loads(content, **kwargs)
            
            # Mise à jour des métriques
            self._update_metrics(path, FileFormat.JSON, compression)
            
            return data

        except Exception as e:
            logger.error(f"Erreur lors de la lecture JSON: {e}")
            raise

    async def _read_yaml(
        self,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> Any:
        """
        Lit un fichier YAML.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments yaml

        Returns:
            Données YAML
        """
        try:
            file_obj = await self._open_file(path, compression)
            content = await file_obj.read()
            
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            data = yaml.safe_load(content, **kwargs)
            
            # Mise à jour des métriques
            self._update_metrics(path, FileFormat.YAML, compression)
            
            return data

        except Exception as e:
            logger.error(f"Erreur lors de la lecture YAML: {e}")
            raise

    async def _read_xml(
        self,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> Any:
        """
        Lit un fichier XML.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments xml

        Returns:
            Données XML
        """
        try:
            import xml.etree.ElementTree as ET
            
            file_obj = await self._open_file(path, compression)
            content = await file_obj.read()
            
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            root = ET.fromstring(content, **kwargs)
            
            # Mise à jour des métriques
            self._update_metrics(path, FileFormat.XML, compression)
            
            return root

        except ImportError:
            logger.error("Module xml.etree.ElementTree non disponible")
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la lecture XML: {e}")
            raise

    async def _read_parquet(
        self,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> pd.DataFrame:
        """
        Lit un fichier Parquet.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas

        Returns:
            DataFrame
        """
        try:
            import pyarrow.parquet as pq
            
            if compression != CompressionType.NONE:
                # D'abord décompresser
                temp_path = await self._decompress_file(path, compression)
                df = pd.read_parquet(temp_path, **kwargs)
                await self._cleanup_temp(temp_path)
            else:
                df = pd.read_parquet(path, **kwargs)
            
            # Mise à jour des métriques
            self._update_metrics(path, FileFormat.PARQUET, compression, len(df))
            
            return df

        except ImportError:
            logger.error("Module pyarrow non disponible")
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la lecture Parquet: {e}")
            raise

    async def _read_excel(
        self,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Lit un fichier Excel.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas

        Returns:
            Dictionnaire des DataFrames par feuille
        """
        try:
            file_obj = await self._open_file(path, compression)
            
            # Lecture avec pandas
            dfs = pd.read_excel(file_obj, sheet_name=None, **kwargs)
            
            # Mise à jour des métriques
            self._update_metrics(path, FileFormat.EXCEL, compression)
            
            return dfs

        except Exception as e:
            logger.error(f"Erreur lors de la lecture Excel: {e}")
            raise

    async def _read_pickle(
        self,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> Any:
        """
        Lit un fichier Pickle.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pickle

        Returns:
            Données pickle
        """
        try:
            file_obj = await self._open_file(path, compression)
            content = await file_obj.read()
            
            data = pickle.loads(content, **kwargs)
            
            # Mise à jour des métriques
            self._update_metrics(path, FileFormat.PICKLE, compression)
            
            return data

        except Exception as e:
            logger.error(f"Erreur lors de la lecture Pickle: {e}")
            raise

    async def _read_hdf5(
        self,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> pd.DataFrame:
        """
        Lit un fichier HDF5.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas

        Returns:
            DataFrame
        """
        try:
            if compression != CompressionType.NONE:
                temp_path = await self._decompress_file(path, compression)
                df = pd.read_hdf(temp_path, **kwargs)
                await self._cleanup_temp(temp_path)
            else:
                df = pd.read_hdf(path, **kwargs)
            
            # Mise à jour des métriques
            self._update_metrics(path, FileFormat.HDF5, compression, len(df))
            
            return df

        except Exception as e:
            logger.error(f"Erreur lors de la lecture HDF5: {e}")
            raise

    async def _read_feather(
        self,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> pd.DataFrame:
        """
        Lit un fichier Feather.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas

        Returns:
            DataFrame
        """
        try:
            if compression != CompressionType.NONE:
                temp_path = await self._decompress_file(path, compression)
                df = pd.read_feather(temp_path, **kwargs)
                await self._cleanup_temp(temp_path)
            else:
                df = pd.read_feather(path, **kwargs)
            
            # Mise à jour des métriques
            self._update_metrics(path, FileFormat.FEATHER, compression, len(df))
            
            return df

        except Exception as e:
            logger.error(f"Erreur lors de la lecture Feather: {e}")
            raise

    # ========================================================================
    # MÉTHODES D'ÉCRITURE
    # ========================================================================

    async def write_file(
        self,
        data: Any,
        file_path: Union[str, Path],
        format: Optional[FileFormat] = None,
        compression: Optional[CompressionType] = None,
        **kwargs
    ) -> Path:
        """
        Écrit un fichier.

        Args:
            data: Données à écrire
            file_path: Chemin du fichier
            format: Format du fichier (optionnel)
            compression: Type de compression (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            Chemin du fichier écrit
        """
        try:
            path = Path(file_path)
            
            # Création du répertoire parent
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Détection automatique du format
            if not format:
                format = self._detect_format(path)
            
            # Détection de la compression
            if not compression:
                compression = self._detect_compression(path)

            # Écriture selon le format
            if format == FileFormat.CSV:
                await self._write_csv(data, path, compression, **kwargs)
            elif format == FileFormat.JSON:
                await self._write_json(data, path, compression, **kwargs)
            elif format == FileFormat.YAML:
                await self._write_yaml(data, path, compression, **kwargs)
            elif format == FileFormat.XML:
                await self._write_xml(data, path, compression, **kwargs)
            elif format == FileFormat.PARQUET:
                await self._write_parquet(data, path, compression, **kwargs)
            elif format == FileFormat.EXCEL:
                await self._write_excel(data, path, compression, **kwargs)
            elif format == FileFormat.PICKLE:
                await self._write_pickle(data, path, compression, **kwargs)
            elif format == FileFormat.HDF5:
                await self._write_hdf5(data, path, compression, **kwargs)
            elif format == FileFormat.FEATHER:
                await self._write_feather(data, path, compression, **kwargs)
            else:
                raise ValueError(f"Format non supporté: {format}")

            # Mise à jour des métriques
            self._metrics["total_files"] += 1
            self._metrics["last_operation"] = datetime.now().isoformat()

            return path

        except Exception as e:
            logger.error(f"Erreur lors de l'écriture du fichier {file_path}: {e}")
            raise

    async def _write_csv(
        self,
        data: Union[pd.DataFrame, List[Dict]],
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> None:
        """
        Écrit un fichier CSV.

        Args:
            data: Données à écrire
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas
        """
        try:
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = data

            if compression != CompressionType.NONE:
                temp_path = path.with_suffix('.tmp')
                df.to_csv(temp_path, index=False, **kwargs)
                await self._compress_file(temp_path, path, compression)
                await self._cleanup_temp(temp_path)
            else:
                df.to_csv(path, index=False, **kwargs)

        except Exception as e:
            logger.error(f"Erreur lors de l'écriture CSV: {e}")
            raise

    async def _write_json(
        self,
        data: Any,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> None:
        """
        Écrit un fichier JSON.

        Args:
            data: Données à écrire
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments json
        """
        try:
            content = json.dumps(data, indent=2, **kwargs)
            content_bytes = content.encode('utf-8')
            
            if compression != CompressionType.NONE:
                compressed = await self._compress_bytes(content_bytes, compression)
                async with aiofiles.open(path, 'wb') as f:
                    await f.write(compressed)
            else:
                async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                    await f.write(content)

        except Exception as e:
            logger.error(f"Erreur lors de l'écriture JSON: {e}")
            raise

    async def _write_yaml(
        self,
        data: Any,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> None:
        """
        Écrit un fichier YAML.

        Args:
            data: Données à écrire
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments yaml
        """
        try:
            content = yaml.dump(data, default_flow_style=False, **kwargs)
            content_bytes = content.encode('utf-8')
            
            if compression != CompressionType.NONE:
                compressed = await self._compress_bytes(content_bytes, compression)
                async with aiofiles.open(path, 'wb') as f:
                    await f.write(compressed)
            else:
                async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                    await f.write(content)

        except Exception as e:
            logger.error(f"Erreur lors de l'écriture YAML: {e}")
            raise

    async def _write_xml(
        self,
        data: Any,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> None:
        """
        Écrit un fichier XML.

        Args:
            data: Données à écrire
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments xml
        """
        try:
            import xml.etree.ElementTree as ET
            
            if isinstance(data, ET.Element):
                content = ET.tostring(data, encoding='unicode')
            else:
                content = str(data)
            
            content_bytes = content.encode('utf-8')
            
            if compression != CompressionType.NONE:
                compressed = await self._compress_bytes(content_bytes, compression)
                async with aiofiles.open(path, 'wb') as f:
                    await f.write(compressed)
            else:
                async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                    await f.write(content)

        except ImportError:
            logger.error("Module xml.etree.ElementTree non disponible")
            raise
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture XML: {e}")
            raise

    async def _write_parquet(
        self,
        data: Union[pd.DataFrame, List[Dict]],
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> None:
        """
        Écrit un fichier Parquet.

        Args:
            data: Données à écrire
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas
        """
        try:
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = data

            if compression != CompressionType.NONE:
                temp_path = path.with_suffix('.tmp')
                df.to_parquet(temp_path, **kwargs)
                await self._compress_file(temp_path, path, compression)
                await self._cleanup_temp(temp_path)
            else:
                df.to_parquet(path, **kwargs)

        except Exception as e:
            logger.error(f"Erreur lors de l'écriture Parquet: {e}")
            raise

    async def _write_excel(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> None:
        """
        Écrit un fichier Excel.

        Args:
            data: Données à écrire
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas
        """
        try:
            if compression != CompressionType.NONE:
                temp_path = path.with_suffix('.tmp')
                
                if isinstance(data, dict):
                    with pd.ExcelWriter(temp_path, engine='openpyxl') as writer:
                        for sheet_name, df in data.items():
                            df.to_excel(writer, sheet_name=sheet_name, **kwargs)
                else:
                    data.to_excel(temp_path, **kwargs)
                
                await self._compress_file(temp_path, path, compression)
                await self._cleanup_temp(temp_path)
            else:
                if isinstance(data, dict):
                    with pd.ExcelWriter(path, engine='openpyxl') as writer:
                        for sheet_name, df in data.items():
                            df.to_excel(writer, sheet_name=sheet_name, **kwargs)
                else:
                    data.to_excel(path, **kwargs)

        except Exception as e:
            logger.error(f"Erreur lors de l'écriture Excel: {e}")
            raise

    async def _write_pickle(
        self,
        data: Any,
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> None:
        """
        Écrit un fichier Pickle.

        Args:
            data: Données à écrire
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pickle
        """
        try:
            content = pickle.dumps(data, **kwargs)
            
            if compression != CompressionType.NONE:
                compressed = await self._compress_bytes(content, compression)
                async with aiofiles.open(path, 'wb') as f:
                    await f.write(compressed)
            else:
                async with aiofiles.open(path, 'wb') as f:
                    await f.write(content)

        except Exception as e:
            logger.error(f"Erreur lors de l'écriture Pickle: {e}")
            raise

    async def _write_hdf5(
        self,
        data: Union[pd.DataFrame, List[Dict]],
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> None:
        """
        Écrit un fichier HDF5.

        Args:
            data: Données à écrire
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas
        """
        try:
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = data

            if compression != CompressionType.NONE:
                temp_path = path.with_suffix('.tmp')
                df.to_hdf(temp_path, key='data', **kwargs)
                await self._compress_file(temp_path, path, compression)
                await self._cleanup_temp(temp_path)
            else:
                df.to_hdf(path, key='data', **kwargs)

        except Exception as e:
            logger.error(f"Erreur lors de l'écriture HDF5: {e}")
            raise

    async def _write_feather(
        self,
        data: Union[pd.DataFrame, List[Dict]],
        path: Path,
        compression: CompressionType,
        **kwargs
    ) -> None:
        """
        Écrit un fichier Feather.

        Args:
            data: Données à écrire
            path: Chemin du fichier
            compression: Type de compression
            **kwargs: Arguments pandas
        """
        try:
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = data

            if compression != CompressionType.NONE:
                temp_path = path.with_suffix('.tmp')
                df.to_feather(temp_path, **kwargs)
                await self._compress_file(temp_path, path, compression)
                await self._cleanup_temp(temp_path)
            else:
                df.to_feather(path, **kwargs)

        except Exception as e:
            logger.error(f"Erreur lors de l'écriture Feather: {e}")
            raise

    # ========================================================================
    # MÉTHODES DE COMPRESSION
    # ========================================================================

    async def _compress_file(
        self,
        source_path: Path,
        dest_path: Path,
        compression: CompressionType
    ) -> None:
        """
        Compresse un fichier.

        Args:
            source_path: Chemin source
            dest_path: Chemin destination
            compression: Type de compression
        """
        try:
            if compression == CompressionType.GZIP:
                async with aiofiles.open(source_path, 'rb') as f_in:
                    content = await f_in.read()
                    compressed = gzip.compress(content)
                    async with aiofiles.open(dest_path, 'wb') as f_out:
                        await f_out.write(compressed)
            
            elif compression == CompressionType.ZIP:
                with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(source_path, source_path.name)
            
            else:
                # Copie simple
                shutil.copy2(source_path, dest_path)

        except Exception as e:
            logger.error(f"Erreur lors de la compression: {e}")
            raise

    async def _decompress_file(
        self,
        source_path: Path,
        compression: CompressionType
    ) -> Path:
        """
        Décompresse un fichier.

        Args:
            source_path: Chemin source
            compression: Type de compression

        Returns:
            Chemin décompressé
        """
        try:
            temp_dir = self.subdirs["temp"]
            temp_path = temp_dir / f"{uuid4()}_{source_path.name}"
            
            if compression == CompressionType.GZIP:
                async with aiofiles.open(source_path, 'rb') as f_in:
                    content = await f_in.read()
                    decompressed = gzip.decompress(content)
                    async with aiofiles.open(temp_path, 'wb') as f_out:
                        await f_out.write(decompressed)
            
            elif compression == CompressionType.ZIP:
                with zipfile.ZipFile(source_path, 'r') as zf:
                    zf.extractall(temp_dir)
                    # Prendre le premier fichier extrait
                    extracted = list(temp_dir.glob("*"))[0]
                    temp_path = extracted
            
            else:
                # Copie simple
                shutil.copy2(source_path, temp_path)
            
            return temp_path

        except Exception as e:
            logger.error(f"Erreur lors de la décompression: {e}")
            raise

    async def _compress_bytes(
        self,
        data: bytes,
        compression: CompressionType
    ) -> bytes:
        """
        Compresse des bytes.

        Args:
            data: Données à compresser
            compression: Type de compression

        Returns:
            Données compressées
        """
        try:
            if compression == CompressionType.GZIP:
                return gzip.compress(data)
            elif compression == CompressionType.ZIP:
                # ZIP nécessite un fichier
                temp_dir = self.subdirs["temp"]
                temp_path = temp_dir / f"{uuid4()}.tmp"
                
                async with aiofiles.open(temp_path, 'wb') as f:
                    await f.write(data)
                
                zip_path = temp_dir / f"{uuid4()}.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(temp_path, "data")
                
                async with aiofiles.open(zip_path, 'rb') as f:
                    compressed = await f.read()
                
                await self._cleanup_temp(temp_path)
                await self._cleanup_temp(zip_path)
                
                return compressed
            else:
                return data

        except Exception as e:
            logger.error(f"Erreur lors de la compression: {e}")
            raise

    async def _cleanup_temp(self, path: Path) -> None:
        """
        Nettoie un fichier temporaire.

        Args:
            path: Chemin du fichier
        """
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logger.warning(f"Erreur lors du nettoyage de {path}: {e}")

    # ========================================================================
    # MÉTHODES DE FICHIER
    # ========================================================================

    async def _open_file(
        self,
        path: Path,
        compression: CompressionType,
        mode: str = 'r'
    ) -> Any:
        """
        Ouvre un fichier avec gestion de la compression.

        Args:
            path: Chemin du fichier
            compression: Type de compression
            mode: Mode d'ouverture

        Returns:
            File object
        """
        if compression == CompressionType.GZIP:
            return gzip.open(path, mode + 'b')
        elif compression == CompressionType.ZIP:
            # Pour ZIP, on extrait et on lit
            temp_path = await self._decompress_file(path, compression)
            return open(temp_path, mode)
        else:
            return open(path, mode)

    def _detect_format(self, path: Path) -> Optional[FileFormat]:
        """
        Détecte le format d'un fichier.

        Args:
            path: Chemin du fichier

        Returns:
            Format détecté
        """
        suffix = ''.join(path.suffixes)
        return self.EXTENSION_MAP.get(suffix)

    def _detect_compression(self, path: Path) -> CompressionType:
        """
        Détecte la compression d'un fichier.

        Args:
            path: Chemin du fichier

        Returns:
            Type de compression
        """
        for ext, comp_type in self.COMPRESSION_EXTENSIONS.items():
            if str(path).endswith(ext):
                return comp_type
        return CompressionType.NONE

    async def get_file_info(self, path: Path) -> FileInfo:
        """
        Récupère les informations d'un fichier.

        Args:
            path: Chemin du fichier

        Returns:
            Informations du fichier
        """
        try:
            if path in self._file_info_cache:
                return self._file_info_cache[path]

            stat = path.stat()
            size_bytes = stat.st_size
            
            file_info = FileInfo(
                path=path,
                name=path.name,
                extension=''.join(path.suffixes),
                size_bytes=size_bytes,
                size_mb=size_bytes / (1024 * 1024),
                size_gb=size_bytes / (1024 * 1024 * 1024),
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                accessed_at=datetime.fromtimestamp(stat.st_atime),
                is_compressed=self._detect_compression(path) != CompressionType.NONE,
                compression_type=self._detect_compression(path),
                checksum=await self.compute_checksum(path),
                format=self._detect_format(path)
            )

            self._file_info_cache[path] = file_info
            return file_info

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des informations du fichier: {e}")
            raise

    async def compute_checksum(
        self,
        path: Path,
        algorithm: str = "sha256"
    ) -> str:
        """
        Calcule le checksum d'un fichier.

        Args:
            path: Chemin du fichier
            algorithm: Algorithme de hachage

        Returns:
            Checksum du fichier
        """
        try:
            hasher = hashlib.new(algorithm)
            
            async with aiofiles.open(path, 'rb') as f:
                while True:
                    chunk = await f.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
            
            return hasher.hexdigest()

        except Exception as e:
            logger.error(f"Erreur lors du calcul du checksum: {e}")
            raise

    def _update_metrics(
        self,
        path: Path,
        format: FileFormat,
        compression: CompressionType,
        row_count: Optional[int] = None
    ) -> None:
        """
        Met à jour les métriques.

        Args:
            path: Chemin du fichier
            format: Format du fichier
            compression: Type de compression
            row_count: Nombre de lignes (optionnel)
        """
        try:
            format_key = format.value
            if format_key not in self._metrics["by_format"]:
                self._metrics["by_format"][format_key] = 0
            self._metrics["by_format"][format_key] += 1

            compression_key = compression.value
            if compression_key not in self._metrics["by_compression"]:
                self._metrics["by_compression"][compression_key] = 0
            self._metrics["by_compression"][compression_key] += 1

            if path.exists():
                self._metrics["total_size_bytes"] += path.stat().st_size

        except Exception as e:
            logger.warning(f"Erreur lors de la mise à jour des métriques: {e}")

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
            total_files = len(list(self.base_directory.rglob('*')))
            
            return {
                "status": "healthy",
                "base_directory": str(self.base_directory),
                "total_files": total_files,
                "total_size_bytes": self._metrics["total_size_bytes"],
                "by_format": self._metrics["by_format"],
                "by_compression": self._metrics["by_compression"],
                "last_operation": self._metrics["last_operation"],
                "cached_metadata": len(self._metadata_cache),
                "cached_file_info": len(self._file_info_cache),
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
        logger.info("Fermeture de FileUtils...")
        self._metadata_cache.clear()
        self._file_info_cache.clear()
        logger.info("FileUtils fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_file_utils(
    base_directory: Optional[str] = None,
    max_file_size: int = 100 * 1024 * 1024
) -> FileUtils:
    """
    Crée une instance de FileUtils.

    Args:
        base_directory: Répertoire de base
        max_file_size: Taille maximale des fichiers

    Returns:
        Instance de FileUtils
    """
    return FileUtils(
        base_directory=base_directory,
        max_file_size=max_file_size
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "FileFormat",
    "CompressionType",
    "FileInfo",
    "FileMetadata",
    "FileUtils",
    "create_file_utils"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation de FileUtils."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT FILE UTILS")
    print("=" * 60)

    # Création de l'instance
    file_utils = create_file_utils(
        base_directory="./data/hedge_bot"
    )

    print(f"\n✅ FileUtils initialisé:")
    print(f"   Base directory: {file_utils.base_directory}")
    print(f"   Sous-répertoires: {list(file_utils.subdirs.keys())}")

    # Données de test
    data = {
        "name": "Hedge Bot",
        "version": "3.0.0",
        "config": {
            "max_hedge_ratio": 0.8,
            "min_hedge_ratio": 0.2
        }
    }

    # Écriture d'un fichier JSON
    json_path = file_utils.base_directory / "test.json"
    await file_utils.write_file(
        data=data,
        file_path=json_path,
        format=FileFormat.JSON
    )
    print(f"\n📝 Fichier JSON écrit: {json_path}")

    # Lecture du fichier JSON
    read_data = await file_utils.read_file(json_path)
    print(f"\n📖 Fichier JSON lu: {read_data}")

    # Écriture d'un fichier CSV
    csv_data = pd.DataFrame([
        {"date": "2026-01-01", "value": 100},
        {"date": "2026-01-02", "value": 105},
        {"date": "2026-01-03", "value": 102}
    ])
    csv_path = file_utils.base_directory / "test.csv"
    await file_utils.write_file(
        data=csv_data,
        file_path=csv_path,
        format=FileFormat.CSV
    )
    print(f"\n📝 Fichier CSV écrit: {csv_path}")

    # Informations du fichier
    file_info = await file_utils.get_file_info(csv_path)
    print(f"\n📊 Informations du fichier:")
    print(f"   Nom: {file_info.name}")
    print(f"   Taille: {file_info.size_mb:.2f} MB")
    print(f"   Format: {file_info.format.value if file_info.format else 'Inconnu'}")
    print(f"   Checksum: {file_info.checksum[:16]}...")

    # Santé du service
    health = await file_utils.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Statut: {health['status']}")
    print(f"   Fichiers: {health['total_files']}")
    print(f"   Taille totale: {health['total_size_bytes'] / (1024*1024):.2f} MB")

    # Fermeture
    await file_utils.close()

    print("\n" + "=" * 60)
    print("FileUtils NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import pandas as pd
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
