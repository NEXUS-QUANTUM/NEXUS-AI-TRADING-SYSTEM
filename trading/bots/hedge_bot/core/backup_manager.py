"""
NEXUS AI TRADING SYSTEM - HEDGE BOT BACKUP MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des sauvegardes pour le Hedge Bot.
Sauvegarde, restauration, compression, et chiffrement des données.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiofiles
import aiofiles.os
import boto3
import paramiko
from azure.storage.blob import BlobServiceClient
from google.cloud import storage
from cryptography.fernet import Fernet
from minio import Minio

from ..utils.helpers import safe_decimal, safe_float, safe_int

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class BackupType(Enum):
    """Types de sauvegarde."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"
    CONFIG = "config"
    DATA = "data"
    LOGS = "logs"
    DATABASE = "database"


class BackupStatus(Enum):
    """Statuts de sauvegarde."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VERIFIED = "verified"


class StorageType(Enum):
    """Types de stockage."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    MINIO = "minio"
    SFTP = "sftp"
    FTP = "ftp"
    WEBDAV = "webdav"
    CUSTOM = "custom"


@dataclass
class BackupMetadata:
    """Métadonnées de sauvegarde."""
    backup_id: UUID
    name: str
    backup_type: BackupType
    status: BackupStatus
    size_bytes: int
    compressed_size_bytes: int
    checksum: str
    path: str
    storage_type: StorageType
    storage_path: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "backup_id": str(self.backup_id),
            "name": self.name,
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "size_bytes": self.size_bytes,
            "compressed_size_bytes": self.compressed_size_bytes,
            "checksum": self.checksum,
            "path": self.path,
            "storage_type": self.storage_type.value,
            "storage_path": self.storage_path,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tags": self.tags,
            "metadata": self.metadata
        }


@dataclass
class RestoreResult:
    """Résultat de restauration."""
    restore_id: UUID
    backup_id: UUID
    status: str
    restored_paths: List[str]
    total_size: int
    duration_seconds: float
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "restore_id": str(self.restore_id),
            "backup_id": str(self.backup_id),
            "status": self.status,
            "restored_paths": self.restored_paths,
            "total_size": self.total_size,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE BACKUP MANAGER
# ============================================================================

class BackupManager:
    """
    Gestionnaire de sauvegardes avancé.
    """

    # Compression par défaut
    DEFAULT_COMPRESSION_LEVEL = 6
    DEFAULT_CHUNK_SIZE = 1024 * 1024 * 10  # 10 MB

    def __init__(
        self,
        base_path: str = "./backups",
        encryption_key: Optional[str] = None,
        redis_client: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de sauvegardes.

        Args:
            base_path: Chemin de base pour les sauvegardes
            encryption_key: Clé de chiffrement
            redis_client: Client Redis pour le cache
            config: Configuration
        """
        self.base_path = Path(base_path)
        self.encryption_key = encryption_key
        self.redis = redis_client
        self.config = config or {}
        
        # Création du répertoire de base
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Sous-répertoires
        self.dirs = {
            "full": self.base_path / "full",
            "incremental": self.base_path / "incremental",
            "snapshot": self.base_path / "snapshot",
            "config": self.base_path / "config",
            "data": self.base_path / "data",
            "logs": self.base_path / "logs",
            "database": self.base_path / "database",
            "temp": self.base_path / "temp"
        }
        
        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Fernet pour chiffrement
        self._fernet = None
        if encryption_key:
            self._fernet = Fernet(encryption_key.encode())
        
        # Clients de stockage
        self._storage_clients: Dict[StorageType, Any] = {}
        
        # Cache
        self._backup_cache: Dict[UUID, BackupMetadata] = {}
        self._restore_cache: Dict[UUID, RestoreResult] = {}
        
        # Métriques
        self._metrics = {
            "total_backups": 0,
            "total_restores": 0,
            "total_size_bytes": 0,
            "total_compressed_bytes": 0,
            "by_type": {},
            "by_status": {},
            "last_backup": None,
            "last_restore": None
        }

        # Initialisation des clients de stockage
        self._init_storage_clients()

        logger.info(f"BackupManager initialisé avec base_path: {base_path}")

    def _init_storage_clients(self) -> None:
        """Initialise les clients de stockage."""
        storage_config = self.config.get("storage", {})
        
        # S3
        if s3_config := storage_config.get("s3"):
            self._storage_clients[StorageType.S3] = boto3.client(
                "s3",
                aws_access_key_id=s3_config.get("access_key"),
                aws_secret_access_key=s3_config.get("secret_key"),
                region_name=s3_config.get("region", "us-east-1"),
                endpoint_url=s3_config.get("endpoint_url")
            )
        
        # GCS
        if gcs_config := storage_config.get("gcs"):
            self._storage_clients[StorageType.GCS] = storage.Client.from_service_account_json(
                gcs_config.get("credentials_file")
            )
        
        # Azure
        if azure_config := storage_config.get("azure"):
            self._storage_clients[StorageType.AZURE] = BlobServiceClient.from_connection_string(
                azure_config.get("connection_string")
            )
        
        # MinIO
        if minio_config := storage_config.get("minio"):
            self._storage_clients[StorageType.MINIO] = Minio(
                minio_config.get("endpoint"),
                access_key=minio_config.get("access_key"),
                secret_key=minio_config.get("secret_key"),
                secure=minio_config.get("secure", True)
            )

    # ========================================================================
    # CRÉATION DE SAUVEGARDE
    # ========================================================================

    async def create_backup(
        self,
        name: str,
        backup_type: BackupType,
        source_paths: List[str],
        destination: Optional[StorageType] = None,
        compress: bool = True,
        encrypt: bool = False,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> BackupMetadata:
        """
        Crée une sauvegarde.

        Args:
            name: Nom de la sauvegarde
            backup_type: Type de sauvegarde
            source_paths: Chemins source
            destination: Type de stockage
            compress: Compresser
            encrypt: Chiffrer
            tags: Tags
            metadata: Métadonnées

        Returns:
            Métadonnées de sauvegarde
        """
        try:
            backup_id = uuid4()
            now = datetime.now()
            
            # Création du répertoire de sauvegarde
            backup_dir = self.dirs[backup_type.value] / str(backup_id)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Copie des fichiers
            total_size = 0
            for source_path in source_paths:
                source = Path(source_path)
                if source.is_file():
                    dest = backup_dir / source.name
                    shutil.copy2(source, dest)
                    total_size += source.stat().st_size
                elif source.is_dir():
                    dest = backup_dir / source.name
                    shutil.copytree(source, dest)
                    total_size += sum(f.stat().st_size for f in source.rglob('*') if f.is_file())

            # Compression
            compressed_size = total_size
            backup_file = backup_dir / f"{backup_id}.tar"
            
            if compress:
                backup_file = await self._compress(backup_dir, backup_file)
                compressed_size = backup_file.stat().st_size

            # Chiffrement
            if encrypt and self._fernet:
                encrypted_file = backup_file.with_suffix(backup_file.suffix + ".enc")
                await self._encrypt_file(backup_file, encrypted_file)
                backup_file.unlink()
                backup_file = encrypted_file
                compressed_size = backup_file.stat().st_size

            # Checksum
            checksum = await self._compute_checksum(backup_file)

            # Stockage externe
            storage_path = str(backup_file)
            if destination:
                storage_path = await self._upload_to_storage(
                    backup_file,
                    destination,
                    f"{backup_type.value}/{backup_id}"
                )

            # Métadonnées
            backup_meta = BackupMetadata(
                backup_id=backup_id,
                name=name,
                backup_type=backup_type,
                status=BackupStatus.COMPLETED,
                size_bytes=total_size,
                compressed_size_bytes=compressed_size,
                checksum=checksum,
                path=str(backup_file),
                storage_type=destination or StorageType.LOCAL,
                storage_path=storage_path,
                created_at=now,
                completed_at=datetime.now(),
                expires_at=now + timedelta(days=self.config.get("retention_days", 30)),
                tags=tags or [],
                metadata=metadata or {}
            )

            # Stockage
            self._backup_cache[backup_id] = backup_meta
            self._metrics["total_backups"] += 1
            self._metrics["total_size_bytes"] += total_size
            self._metrics["total_compressed_bytes"] += compressed_size
            self._metrics["last_backup"] = now.isoformat()

            backup_type_key = backup_type.value
            if backup_type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][backup_type_key] = 0
            self._metrics["by_type"][backup_type_key] += 1

            # Sauvegarde Redis
            if self.redis:
                await self._save_backup_metadata(backup_meta)

            logger.info(f"Sauvegarde créée: {backup_id} - {name}")
            return backup_meta

        except Exception as e:
            logger.error(f"Erreur lors de la création de la sauvegarde: {e}")
            raise

    async def _compress(self, source_dir: Path, output_file: Path) -> Path:
        """
        Compresse un répertoire.

        Args:
            source_dir: Répertoire source
            output_file: Fichier de sortie

        Returns:
            Fichier compressé
        """
        try:
            import tarfile
            
            output_file = output_file.with_suffix('.tar.gz')
            
            with tarfile.open(output_file, "w:gz") as tar:
                tar.add(source_dir, arcname=source_dir.name)
            
            return output_file

        except Exception as e:
            logger.error(f"Erreur de compression: {e}")
            raise

    async def _encrypt_file(self, source: Path, destination: Path) -> None:
        """
        Chiffre un fichier.

        Args:
            source: Fichier source
            destination: Fichier destination
        """
        try:
            async with aiofiles.open(source, 'rb') as f_in:
                data = await f_in.read()
                encrypted = self._fernet.encrypt(data)
                
                async with aiofiles.open(destination, 'wb') as f_out:
                    await f_out.write(encrypted)
        except Exception as e:
            logger.error(f"Erreur de chiffrement: {e}")
            raise

    async def _decrypt_file(self, source: Path, destination: Path) -> None:
        """
        Déchiffre un fichier.

        Args:
            source: Fichier source
            destination: Fichier destination
        """
        try:
            async with aiofiles.open(source, 'rb') as f_in:
                encrypted = await f_in.read()
                decrypted = self._fernet.decrypt(encrypted)
                
                async with aiofiles.open(destination, 'wb') as f_out:
                    await f_out.write(decrypted)
        except Exception as e:
            logger.error(f"Erreur de déchiffrement: {e}")
            raise

    async def _compute_checksum(self, file_path: Path, algorithm: str = "sha256") -> str:
        """
        Calcule le checksum d'un fichier.

        Args:
            file_path: Chemin du fichier
            algorithm: Algorithme de hachage

        Returns:
            Checksum
        """
        try:
            hasher = hashlib.new(algorithm)
            chunk_size = self.DEFAULT_CHUNK_SIZE
            
            async with aiofiles.open(file_path, 'rb') as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            
            return hasher.hexdigest()

        except Exception as e:
            logger.error(f"Erreur de calcul de checksum: {e}")
            raise

    # ========================================================================
    # RESTAURATION
    # ========================================================================

    async def restore(
        self,
        backup_id: UUID,
        destination_path: Optional[str] = None,
        decrypt: bool = True,
        decompress: bool = True,
        metadata: Optional[Dict] = None
    ) -> RestoreResult:
        """
        Restaure une sauvegarde.

        Args:
            backup_id: ID de la sauvegarde
            destination_path: Chemin de destination
            decrypt: Déchiffrer
            decompress: Décompresser
            metadata: Métadonnées

        Returns:
            Résultat de restauration
        """
        try:
            backup = await self.get_backup(backup_id)
            if not backup:
                raise ValueError(f"Sauvegarde {backup_id} non trouvée")

            restore_id = uuid4()
            now = datetime.now()
            start_time = datetime.now()

            destination = Path(destination_path or "restore")
            destination.mkdir(parents=True, exist_ok=True)

            restored_paths = []
            total_size = 0

            # Récupération du fichier
            file_path = Path(backup.path)
            
            # Téléchargement si nécessaire
            if backup.storage_type != StorageType.LOCAL:
                file_path = await self._download_from_storage(
                    backup.storage_type,
                    backup.storage_path,
                    self.dirs["temp"] / f"{backup_id}.restore"
                )

            # Déchiffrement
            if decrypt and self._fernet and str(file_path).endswith('.enc'):
                decrypted_path = file_path.with_suffix('')
                await self._decrypt_file(file_path, decrypted_path)
                file_path.unlink()
                file_path = decrypted_path

            # Décompression
            if decompress and str(file_path).endswith(('.tar.gz', '.tar')):
                import tarfile
                
                with tarfile.open(file_path, "r:gz") if str(file_path).endswith('.gz') else tarfile.open(file_path, "r") as tar:
                    tar.extractall(destination)
                    
                restored_paths = [str(destination / name) for name in tar.getnames()]
                total_size = sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())
                file_path.unlink()
            else:
                # Copie simple
                shutil.copy2(file_path, destination / file_path.name)
                restored_paths = [str(destination / file_path.name)]
                total_size = file_path.stat().st_size

            duration = (datetime.now() - start_time).total_seconds()

            result = RestoreResult(
                restore_id=restore_id,
                backup_id=backup_id,
                status="completed",
                restored_paths=restored_paths,
                total_size=total_size,
                duration_seconds=duration,
                created_at=now,
                completed_at=datetime.now(),
                metadata=metadata or {}
            )

            self._restore_cache[restore_id] = result
            self._metrics["total_restores"] += 1
            self._metrics["last_restore"] = now.isoformat()

            logger.info(f"Restauration terminée: {restore_id}")
            return result

        except Exception as e:
            logger.error(f"Erreur lors de la restauration: {e}")
            raise

    # ========================================================================
    # STOCKAGE
    # ========================================================================

    async def _upload_to_storage(
        self,
        file_path: Path,
        storage_type: StorageType,
        remote_path: str
    ) -> str:
        """
        Upload un fichier vers un stockage.

        Args:
            file_path: Chemin du fichier
            storage_type: Type de stockage
            remote_path: Chemin distant

        Returns:
            Chemin distant
        """
        try:
            client = self._storage_clients.get(storage_type)
            if not client:
                raise ValueError(f"Client de stockage non trouvé pour {storage_type}")

            if storage_type == StorageType.S3:
                bucket = self.config.get("storage", {}).get("s3", {}).get("bucket")
                client.upload_file(str(file_path), bucket, remote_path)
                return f"s3://{bucket}/{remote_path}"

            elif storage_type == StorageType.GCS:
                bucket = client.bucket(self.config.get("storage", {}).get("gcs", {}).get("bucket"))
                blob = bucket.blob(remote_path)
                blob.upload_from_filename(str(file_path))
                return f"gs://{bucket.name}/{remote_path}"

            elif storage_type == StorageType.AZURE:
                container = self.config.get("storage", {}).get("azure", {}).get("container")
                blob_client = client.get_blob_client(container=container, blob=remote_path)
                with open(file_path, "rb") as data:
                    blob_client.upload_blob(data)
                return f"azure://{container}/{remote_path}"

            elif storage_type == StorageType.MINIO:
                bucket = self.config.get("storage", {}).get("minio", {}).get("bucket")
                client.fput_object(bucket, remote_path, str(file_path))
                return f"minio://{bucket}/{remote_path}"

            else:
                return str(file_path)

        except Exception as e:
            logger.error(f"Erreur d'upload: {e}")
            raise

    async def _download_from_storage(
        self,
        storage_type: StorageType,
        remote_path: str,
        local_path: Path
    ) -> Path:
        """
        Download un fichier depuis un stockage.

        Args:
            storage_type: Type de stockage
            remote_path: Chemin distant
            local_path: Chemin local

        Returns:
            Chemin local
        """
        try:
            client = self._storage_clients.get(storage_type)
            if not client:
                raise ValueError(f"Client de stockage non trouvé pour {storage_type}")

            if storage_type == StorageType.S3:
                bucket = self.config.get("storage", {}).get("s3", {}).get("bucket")
                client.download_file(bucket, remote_path.split('/')[-1], str(local_path))
                return local_path

            elif storage_type == StorageType.GCS:
                bucket = client.bucket(self.config.get("storage", {}).get("gcs", {}).get("bucket"))
                blob = bucket.blob(remote_path.split('/')[-1])
                blob.download_to_filename(str(local_path))
                return local_path

            elif storage_type == StorageType.AZURE:
                container = self.config.get("storage", {}).get("azure", {}).get("container")
                blob_client = client.get_blob_client(container=container, blob=remote_path.split('/')[-1])
                with open(local_path, "wb") as data:
                    blob_data = blob_client.download_blob()
                    blob_data.readinto(data)
                return local_path

            elif storage_type == StorageType.MINIO:
                bucket = self.config.get("storage", {}).get("minio", {}).get("bucket")
                client.fget_object(bucket, remote_path.split('/')[-1], str(local_path))
                return local_path

            else:
                return local_path

        except Exception as e:
            logger.error(f"Erreur de download: {e}")
            raise

    # ========================================================================
    # RÉCUPÉRATION
    # ========================================================================

    async def get_backup(
        self,
        backup_id: UUID
    ) -> Optional[BackupMetadata]:
        """
        Récupère une sauvegarde.

        Args:
            backup_id: ID de la sauvegarde

        Returns:
            Métadonnées de sauvegarde
        """
        return self._backup_cache.get(backup_id)

    async def get_backups(
        self,
        backup_type: Optional[BackupType] = None,
        status: Optional[BackupStatus] = None,
        tags: Optional[List[str]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[BackupMetadata]:
        """
        Récupère les sauvegardes.

        Args:
            backup_type: Filtrer par type
            status: Filtrer par statut
            tags: Filtrer par tags
            from_date: Date de début
            to_date: Date de fin
            limit: Nombre de sauvegardes
            offset: Décalage

        Returns:
            Liste des sauvegardes
        """
        backups = list(self._backup_cache.values())

        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]
        if status:
            backups = [b for b in backups if b.status == status]
        if tags:
            backups = [b for b in backups if any(t in b.tags for t in tags)]
        if from_date:
            backups = [b for b in backups if b.created_at >= from_date]
        if to_date:
            backups = [b for b in backups if b.created_at <= to_date]

        backups.sort(key=lambda x: x.created_at, reverse=True)
        return backups[offset:offset + limit]

    async def get_restore_result(
        self,
        restore_id: UUID
    ) -> Optional[RestoreResult]:
        """
        Récupère un résultat de restauration.

        Args:
            restore_id: ID de la restauration

        Returns:
            Résultat de restauration
        """
        return self._restore_cache.get(restore_id)

    # ========================================================================
    # MAINTENANCE
    # ========================================================================

    async def cleanup(
        self,
        older_than_days: int = 30,
        max_backups: int = 10
    ) -> Dict[str, Any]:
        """
        Nettoie les anciennes sauvegardes.

        Args:
            older_than_days: Âge maximum
            max_backups: Nombre maximum de sauvegardes

        Returns:
            Résultat du nettoyage
        """
        try:
            cutoff = datetime.now() - timedelta(days=older_than_days)
            deleted = []
            freed_space = 0

            backups = await self.get_backups()
            backups.sort(key=lambda x: x.created_at)

            # Suppression des anciennes
            for backup in backups:
                if backup.created_at < cutoff or len(backups) > max_backups:
                    # Suppression du fichier
                    if Path(backup.path).exists():
                        freed_space += Path(backup.path).stat().st_size
                        Path(backup.path).unlink()
                    
                    # Suppression des métadonnées
                    if backup.backup_id in self._backup_cache:
                        del self._backup_cache[backup.backup_id]
                    
                    deleted.append(str(backup.backup_id))
                    backups.remove(backup)

            return {
                "deleted_count": len(deleted),
                "deleted_ids": deleted,
                "freed_space_bytes": freed_space,
                "freed_space_mb": freed_space / (1024 * 1024),
                "freed_space_gb": freed_space / (1024 * 1024 * 1024)
            }

        except Exception as e:
            logger.error(f"Erreur de nettoyage: {e}")
            return {"error": str(e)}

    # ========================================================================
    # STOCKAGE
    # ========================================================================

    async def _save_backup_metadata(self, backup: BackupMetadata) -> None:
        """
        Sauvegarde les métadonnées dans Redis.

        Args:
            backup: Métadonnées à sauvegarder
        """
        try:
            key = f"backup:{backup.backup_id}"
            await self.redis.setex(
                key,
                86400 * self.config.get("retention_days", 30),
                json.dumps(backup.to_dict())
            )
        except Exception as e:
            logger.error(f"Erreur de sauvegarde Redis: {e}")

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
                "total_backups": self._metrics["total_backups"],
                "total_restores": self._metrics["total_restores"],
                "total_size_bytes": self._metrics["total_size_bytes"],
                "total_compressed_bytes": self._metrics["total_compressed_bytes"],
                "by_type": self._metrics["by_type"],
                "by_status": self._metrics["by_status"],
                "last_backup": self._metrics["last_backup"],
                "last_restore": self._metrics["last_restore"],
                "cached_backups": len(self._backup_cache),
                "cached_restores": len(self._restore_cache),
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
        logger.info("Fermeture de BackupManager...")
        self._backup_cache.clear()
        self._restore_cache.clear()
        self._storage_clients.clear()
        logger.info("BackupManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_backup_manager(
    base_path: str = "./backups",
    encryption_key: Optional[str] = None,
    redis_url: str = "redis://localhost:6379/0",
    config: Optional[Dict[str, Any]] = None
) -> BackupManager:
    """
    Crée une instance de BackupManager.

    Args:
        base_path: Chemin de base
        encryption_key: Clé de chiffrement
        redis_url: URL de connexion Redis
        config: Configuration

    Returns:
        Instance de BackupManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return BackupManager(
        base_path=base_path,
        encryption_key=encryption_key,
        redis_client=redis_client,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "BackupType",
    "BackupStatus",
    "StorageType",
    "BackupMetadata",
    "RestoreResult",
    "BackupManager",
    "create_backup_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire de sauvegardes."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT BACKUP MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    backup_manager = create_backup_manager(
        base_path="./backups",
        encryption_key="your-encryption-key-32-bytes"
    )

    print(f"\n✅ BackupManager initialisé")

    # Création d'une sauvegarde
    print(f"\n📦 Création d'une sauvegarde...")
    
    # Création d'un fichier de test
    test_file = Path("test_data.txt")
    test_file.write_text("Données de test pour la sauvegarde")
    
    backup = await backup_manager.create_backup(
        name="Test Backup",
        backup_type=BackupType.FULL,
        source_paths=[str(test_file)],
        compress=True,
        encrypt=True,
        tags=["test", "example"],
        metadata={"description": "Sauvegarde de test"}
    )

    print(f"   ID: {backup.backup_id}")
    print(f"   Nom: {backup.name}")
    print(f"   Type: {backup.backup_type.value}")
    print(f"   Taille: {backup.compressed_size_bytes / 1024:.2f} KB")
    print(f"   Checksum: {backup.checksum[:16]}...")

    # Nettoyage du fichier de test
    test_file.unlink()

    # Restauration
    print(f"\n🔄 Restauration de la sauvegarde...")
    restore = await backup_manager.restore(
        backup_id=backup.backup_id,
        destination_path="./restored"
    )

    print(f"   ID: {restore.restore_id}")
    print(f"   Statut: {restore.status}")
    print(f"   Fichiers restaurés: {len(restore.restored_paths)}")
    print(f"   Durée: {restore.duration_seconds:.2f}s")

    # Récupération des sauvegardes
    print(f"\n📋 Liste des sauvegardes:")
    backups = await backup_manager.get_backups(limit=5)
    for b in backups[:3]:
        print(f"   {b.created_at.strftime('%Y-%m-%d %H:%M')}: {b.name} ({b.backup_type.value})")

    # Nettoyage
    print(f"\n🧹 Nettoyage des sauvegardes...")
    cleanup = await backup_manager.cleanup(older_than_days=1)
    print(f"   Supprimées: {cleanup['deleted_count']}")
    print(f"   Espace libéré: {cleanup['freed_space_mb']:.2f} MB")

    # Santé du service
    health = await backup_manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Sauvegardes: {health['total_backups']}")
    print(f"   Restaurations: {health['total_restores']}")
    print(f"   Taille totale: {health['total_size_bytes'] / (1024*1024):.2f} MB")

    # Fermeture
    await backup_manager.close()

    print("\n" + "=" * 60)
    print("BackupManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
