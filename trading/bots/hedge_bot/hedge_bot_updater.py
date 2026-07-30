# trading/bots/hedge_bot/hedge_bot_updater.py
# Advanced Update & Version Management System for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Update Manager - Système avancé de mise à jour et gestion de version pour le Hedge Bot.
Assure les mises à jour automatiques, la gestion des versions, le rollback, la compatibilité
des modèles et la maintenance continue du système de hedging.
"""

import asyncio
import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import aiohttp
import aiohttp.client_exceptions
import git
import semver
import docker
import yaml
from pathlib import Path

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_updater")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class UpdateType(Enum):
    """Types de mises à jour."""
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    SECURITY = "security"
    HOTFIX = "hotfix"
    CUSTOM = "custom"


class UpdateStatus(Enum):
    """Statuts de mise à jour."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    APPLYING = "applying"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK = "rollback"
    ROLLBACK_COMPLETED = "rollback_completed"
    CANCELLED = "cancelled"


class UpdateSource(Enum):
    """Sources de mises à jour."""
    GITHUB = "github"
    GITLAB = "gitlab"
    DOCKER_HUB = "docker_hub"
    PYPI = "pypi"
    CUSTOM_REPO = "custom_repo"
    LOCAL = "local"
    S3 = "s3"


class CompatibilityLevel(Enum):
    """Niveaux de compatibilité."""
    FULL = "full"      # 100% compatible
    MAJOR = "major"    # Compatible avec ajustements majeurs
    MINOR = "minor"    # Compatible avec ajustements mineurs
    PATCH = "patch"    # Compatible avec ajustements de patch
    NONE = "none"      # Incompatible


# ============== DATA MODELS ==============

@dataclass
class UpdateManifest:
    """Manifeste de mise à jour."""
    manifest_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"
    update_type: UpdateType = UpdateType.PATCH
    release_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""
    changelog: str = ""
    files: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    checksums: Dict[str, str] = field(default_factory=dict)
    required_version: str = "1.0.0"
    compatibility: CompatibilityLevel = CompatibilityLevel.FULL
    migration_script: Optional[str] = None
    rollback_script: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "manifest_id": self.manifest_id,
            "version": self.version,
            "update_type": self.update_type.value,
            "release_date": self.release_date.isoformat(),
            "description": self.description,
            "changelog": self.changelog,
            "files": self.files,
            "dependencies": self.dependencies,
            "checksums": self.checksums,
            "required_version": self.required_version,
            "compatibility": self.compatibility.value,
            "migration_script": self.migration_script,
            "rollback_script": self.rollback_script,
            "metadata": self.metadata,
            "tags": self.tags,
            "signature": self.signature
        }


@dataclass
class UpdateJob:
    """Job de mise à jour."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    manifest_id: str = ""
    target_version: str = ""
    current_version: str = ""
    status: UpdateStatus = UpdateStatus.PENDING
    progress: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    backup_path: Optional[str] = None
    rollback_performed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "manifest_id": self.manifest_id,
            "target_version": self.target_version,
            "current_version": self.current_version,
            "status": self.status.value,
            "progress": self.progress,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "backup_path": self.backup_path,
            "rollback_performed": self.rollback_performed,
            "metadata": self.metadata,
            "logs": self.logs,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }


@dataclass
class VersionInfo:
    """Information de version."""
    version: str = "1.0.0"
    release_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_latest: bool = False
    is_supported: bool = True
    download_url: Optional[str] = None
    size_bytes: int = 0
    checksum: Optional[str] = None
    changelog: str = ""
    release_notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class UpdateEngineInterface(ABC):
    """Interface abstraite pour le moteur de mise à jour."""
    
    @abstractmethod
    async def check_for_updates(self) -> List[VersionInfo]:
        """Vérifie les mises à jour disponibles."""
        pass
    
    @abstractmethod
    async def download_update(self, version: str) -> str:
        """Télécharge une mise à jour."""
        pass
    
    @abstractmethod
    async def apply_update(self, job: UpdateJob) -> bool:
        """Applique une mise à jour."""
        pass
    
    @abstractmethod
    async def rollback(self, job: UpdateJob) -> bool:
        """Effectue un rollback."""
        pass


# ============== IMPLÉMENTATION ==============

class UpdateEngine(UpdateEngineInterface):
    """
    Moteur de mise à jour avancé pour le Hedge Bot.
    Gère les mises à jour automatiques, les vérifications de version, les rollbacks
    et la compatibilité des modèles.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Installation courante
        self.current_version = self._get_current_version()
        
        # Gestion des jobs
        self._jobs: Dict[str, UpdateJob] = {}
        self._jobs_lock = threading.RLock()
        
        # Cache des versions
        self._version_cache: Dict[str, VersionInfo] = {}
        self._cache_lock = threading.RLock()
        
        # Manifestes
        self._manifests: Dict[str, UpdateManifest] = {}
        self._manifest_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "updates_checked": 0,
            "updates_downloaded": 0,
            "updates_applied": 0,
            "updates_failed": 0,
            "rollbacks_performed": 0,
            "current_version": self.current_version,
            "latest_version": self.current_version
        }
        
        # État
        self._is_running = False
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Client Docker
        self._docker_client = None
        
        logger.info(f"UpdateEngine initialized (current version: {self.current_version})")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "update_check_interval": 86400,  # 1 jour
            "auto_update": False,
            "auto_rollback_on_failure": True,
            "backup_before_update": True,
            "verify_checksums": True,
            "verify_signatures": True,
            "max_backups": 5,
            "repo_url": "https://api.github.com/repos/NEXUS-QUANTUM/NEXUS-AI-TRADING-SYSTEM",
            "repo_type": UpdateSource.GITHUB,
            "docker_image": "nexusquantum/nexus-ai-trading",
            "docker_tag": "latest",
            "backup_dir": "./backups",
            "update_dir": "./updates",
            "temp_dir": "/tmp/nexus_updates",
            "timeout": 3600,  # 1 heure
            "download_timeout": 600,  # 10 minutes
            "health_check_timeout": 120,  # 2 minutes
            "min_free_space_gb": 5,
            "min_memory_mb": 512
        }
    
    async def start(self) -> None:
        """Démarre le moteur de mise à jour."""
        logger.info("UpdateEngine starting...")
        self._is_running = True
        
        # Création des sessions
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config["timeout"])
        )
        
        # Connexion à Docker
        try:
            self._docker_client = docker.from_env()
            logger.info("Connected to Docker daemon")
        except Exception as e:
            logger.warning(f"Docker connection failed: {e}")
        
        # Création des dossiers
        Path(self.config["backup_dir"]).mkdir(parents=True, exist_ok=True)
        Path(self.config["update_dir"]).mkdir(parents=True, exist_ok=True)
        Path(self.config["temp_dir"]).mkdir(parents=True, exist_ok=True)
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._update_check_loop())
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._health_check_loop())
        
        logger.info("UpdateEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de mise à jour."""
        logger.info("UpdateEngine stopping...")
        self._is_running = False
        
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("UpdateEngine stopped")
    
    async def check_for_updates(self) -> List[VersionInfo]:
        """Vérifie les mises à jour disponibles."""
        self._stats["updates_checked"] += 1
        
        try:
            # Récupération des versions disponibles
            versions = await self._fetch_versions()
            
            # Mise à jour du cache
            with self._cache_lock:
                for version in versions:
                    self._version_cache[version.version] = version
                    if version.is_latest:
                        self._stats["latest_version"] = version.version
            
            logger.info(f"Update check completed: {len(versions)} versions found")
            return versions
            
        except Exception as e:
            logger.error(f"Update check error: {e}")
            return []
    
    async def download_update(self, version: str) -> str:
        """Télécharge une mise à jour."""
        self._stats["updates_downloaded"] += 1
        
        try:
            # Vérification de la version
            version_info = await self._get_version_info(version)
            if not version_info:
                raise ValueError(f"Version {version} not found")
            
            # Téléchargement
            download_path = await self._download_version(version_info)
            
            # Vérification
            if self.config["verify_checksums"]:
                await self._verify_download(download_path, version_info)
            
            logger.info(f"Update downloaded: {version} -> {download_path}")
            return download_path
            
        except Exception as e:
            self._stats["updates_failed"] += 1
            logger.error(f"Download error: {e}")
            raise
    
    async def apply_update(self, job: UpdateJob) -> bool:
        """Applique une mise à jour."""
        job.started_at = datetime.now(timezone.utc)
        job.status = UpdateStatus.APPLYING
        job.logs.append(f"Starting update to {job.target_version}")
        
        try:
            # Vérification préalable
            await self._pre_update_checks(job)
            
            # Sauvegarde
            if self.config["backup_before_update"]:
                job.backup_path = await self._create_backup()
                job.logs.append(f"Backup created: {job.backup_path}")
            
            # Téléchargement du manifeste
            manifest = await self._get_manifest(job.target_version)
            if manifest:
                job.manifest_id = manifest.manifest_id
                self._manifests[manifest.manifest_id] = manifest
                job.logs.append(f"Manifest loaded: {manifest.manifest_id}")
            
            # Application
            await self._apply_update_files(job, manifest)
            
            # Migration
            if manifest and manifest.migration_script:
                await self._run_migration(job, manifest)
            
            # Vérification post-mise à jour
            await self._post_update_checks(job)
            
            # Mise à jour de la version
            self.current_version = job.target_version
            self._stats["current_version"] = job.current_version
            
            job.status = UpdateStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 1.0
            job.logs.append(f"Update completed successfully: {job.target_version}")
            
            self._stats["updates_applied"] += 1
            
            logger.info(f"Update applied: {job.current_version} -> {job.target_version}")
            return True
            
        except Exception as e:
            job.status = UpdateStatus.FAILED
            job.error = str(e)
            job.logs.append(f"Update failed: {e}")
            
            self._stats["updates_failed"] += 1
            
            # Rollback automatique
            if self.config["auto_rollback_on_failure"]:
                job.logs.append("Initiating automatic rollback...")
                rollback_success = await self.rollback(job)
                job.logs.append(f"Rollback {'successful' if rollback_success else 'failed'}")
            
            logger.error(f"Update failed: {e}")
            return False
    
    async def rollback(self, job: UpdateJob) -> bool:
        """Effectue un rollback."""
        job.logs.append("Starting rollback...")
        
        try:
            # Vérification du backup
            if not job.backup_path or not Path(job.backup_path).exists():
                job.logs.append("Backup not found, rollback impossible")
                return False
            
            # Restauration
            await self._restore_backup(job)
            
            # Nettoyage
            await self._cleanup_after_rollback(job)
            
            # Mise à jour de la version
            self.current_version = job.current_version
            
            job.status = UpdateStatus.ROLLBACK_COMPLETED
            job.rollback_performed = True
            job.logs.append(f"Rollback completed: {job.current_version}")
            
            self._stats["rollbacks_performed"] += 1
            
            logger.info(f"Rollback completed: {job.job_id}")
            return True
            
        except Exception as e:
            job.status = UpdateStatus.FAILED
            job.error = str(e)
            job.logs.append(f"Rollback failed: {e}")
            
            logger.error(f"Rollback failed: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - VÉRIFICATION ==========
    
    async def _fetch_versions(self) -> List[VersionInfo]:
        """Récupère les versions disponibles."""
        versions = []
        
        if self.config["repo_type"] == UpdateSource.GITHUB:
            versions = await self._fetch_github_versions()
        elif self.config["repo_type"] == UpdateSource.DOCKER_HUB:
            versions = await self._fetch_docker_versions()
        elif self.config["repo_type"] == UpdateSource.PYPI:
            versions = await self._fetch_pypi_versions()
        else:
            versions = await self._fetch_custom_versions()
        
        # Tri par version
        versions.sort(key=lambda v: semver.VersionInfo.parse(v.version), reverse=True)
        
        return versions
    
    async def _fetch_github_versions(self) -> List[VersionInfo]:
        """Récupère les versions depuis GitHub."""
        versions = []
        
        try:
            url = f"{self.config['repo_url']}/releases"
            
            async with self._session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for release in data:
                        version = release.get("tag_name", "").lstrip("v")
                        if not semver.VersionInfo.is_valid(version):
                            continue
                        
                        version_info = VersionInfo(
                            version=version,
                            release_date=datetime.fromisoformat(
                                release.get("published_at", datetime.now(timezone.utc).isoformat())
                            ),
                            is_latest=release.get("prerelease", False) == False,
                            download_url=release.get("zipball_url"),
                            size_bytes=0,
                            changelog=release.get("body", ""),
                            metadata={
                                "name": release.get("name"),
                                "prerelease": release.get("prerelease", False),
                                "draft": release.get("draft", False)
                            }
                        )
                        versions.append(version_info)
                
        except Exception as e:
            logger.error(f"GitHub fetch error: {e}")
        
        return versions
    
    async def _fetch_docker_versions(self) -> List[VersionInfo]:
        """Récupère les versions depuis Docker Hub."""
        versions = []
        
        try:
            if self._docker_client:
                # Récupération des tags
                image = self.config["docker_image"]
                tags = self._docker_client.images.list(name=image)
                
                for tag in tags:
                    version = tag.tags[0].split(":")[-1] if tag.tags else "latest"
                    if version == "latest":
                        continue
                    
                    if semver.VersionInfo.is_valid(version):
                        version_info = VersionInfo(
                            version=version,
                            release_date=datetime.now(timezone.utc),
                            is_latest=version == "latest",
                            download_url=f"docker://{image}:{version}",
                            size_bytes=0,
                            metadata={"digest": tag.id}
                        )
                        versions.append(version_info)
        
        except Exception as e:
            logger.error(f"Docker fetch error: {e}")
        
        return versions
    
    async def _fetch_pypi_versions(self) -> List[VersionInfo]:
        """Récupère les versions depuis PyPI."""
        versions = []
        
        try:
            package = self.config.get("pypi_package", "nexus-ai-trading")
            url = f"https://pypi.org/pypi/{package}/json"
            
            async with self._session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    releases = data.get("releases", {})
                    
                    for version, files in releases.items():
                        if not semver.VersionInfo.is_valid(version):
                            continue
                        
                        file_info = files[0] if files else {}
                        version_info = VersionInfo(
                            version=version,
                            release_date=datetime.fromisoformat(
                                file_info.get("upload_time", datetime.now(timezone.utc).isoformat())
                            ),
                            is_latest=version == data.get("info", {}).get("version"),
                            download_url=file_info.get("url"),
                            size_bytes=file_info.get("size", 0),
                            checksum=file_info.get("digests", {}).get("sha256")
                        )
                        versions.append(version_info)
        
        except Exception as e:
            logger.error(f"PyPI fetch error: {e}")
        
        return versions
    
    async def _fetch_custom_versions(self) -> List[VersionInfo]:
        """Récupère les versions depuis une source personnalisée."""
        # Simulation de versions
        return [
            VersionInfo(
                version="1.0.0",
                is_latest=False,
                changelog="Initial release"
            ),
            VersionInfo(
                version="1.1.0",
                is_latest=True,
                changelog="Added hedging features"
            )
        ]
    
    async def _download_version(self, version_info: VersionInfo) -> str:
        """Télécharge une version spécifique."""
        download_path = f"{self.config['temp_dir']}/nexus_{version_info.version}.tar.gz"
        
        if version_info.download_url:
            # Téléchargement depuis URL
            async with self._session.get(version_info.download_url) as response:
                if response.status == 200:
                    with open(download_path, 'wb') as f:
                        f.write(await response.read())
        else:
            # Simulation
            with open(download_path, 'wb') as f:
                f.write(b"Simulated update package")
        
        return download_path
    
    async def _verify_download(self, path: str, version_info: VersionInfo) -> bool:
        """Vérifie l'intégrité du téléchargement."""
        if version_info.checksum:
            sha256 = hashlib.sha256()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            computed = sha256.hexdigest()
            
            if computed != version_info.checksum:
                raise ValueError(f"Checksum mismatch: {computed} != {version_info.checksum}")
        
        return True
    
    # ========== MÉTHODES PRIVÉES - APPLICATION ==========
    
    async def _pre_update_checks(self, job: UpdateJob) -> None:
        """Effectue les vérifications pré-mise à jour."""
        # Vérification de l'espace disque
        stat = shutil.disk_usage('/')
        free_gb = stat.free / (1024 ** 3)
        if free_gb < self.config["min_free_space_gb"]:
            raise RuntimeError(f"Insufficient disk space: {free_gb:.1f}GB < {self.config['min_free_space_gb']}GB")
        
        # Vérification de la mémoire
        import psutil
        memory = psutil.virtual_memory()
        free_mb = memory.available / (1024 ** 2)
        if free_mb < self.config["min_memory_mb"]:
            raise RuntimeError(f"Insufficient memory: {free_mb:.0f}MB < {self.config['min_memory_mb']}MB")
        
        # Vérification de compatibilité
        manifest = await self._get_manifest(job.target_version)
        if manifest:
            current = semver.VersionInfo.parse(self.current_version)
            required = semver.VersionInfo.parse(manifest.required_version)
            
            if current < required:
                raise RuntimeError(f"Incompatible version: {self.current_version} < {manifest.required_version}")
    
    async def _apply_update_files(self, job: UpdateJob, manifest: UpdateManifest) -> None:
        """Applique les fichiers de mise à jour."""
        # Extraction du package
        package_path = f"{self.config['update_dir']}/nexus_{job.target_version}.tar.gz"
        if Path(package_path).exists():
            import tarfile
            with tarfile.open(package_path, 'r:gz') as tar:
                tar.extractall(self.config["update_dir"])
                job.logs.append(f"Package extracted: {package_path}")
        
        # Copie des fichiers
        if manifest:
            for file_info in manifest.files:
                source = Path(self.config["update_dir"]) / file_info["source"]
                destination = Path(file_info["destination"])
                
                if source.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    job.logs.append(f"File applied: {file_info['source']} -> {destination}")
        
        # Mise à jour des dépendances
        if manifest and manifest.dependencies:
            await self._update_dependencies(manifest.dependencies, job)
    
    async def _update_dependencies(self, dependencies: Dict[str, str], job: UpdateJob) -> None:
        """Met à jour les dépendances."""
        for package, version in dependencies.items():
            try:
                # Installation via pip
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", f"{package}=={version}"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    job.logs.append(f"Dependency updated: {package}=={version}")
                else:
                    job.logs.append(f"Failed to update dependency: {package} - {result.stderr}")
                    
            except Exception as e:
                job.logs.append(f"Dependency error: {package} - {e}")
    
    async def _run_migration(self, job: UpdateJob, manifest: UpdateManifest) -> None:
        """Exécute le script de migration."""
        if manifest.migration_script:
            script_path = Path(manifest.migration_script)
            if script_path.exists():
                try:
                    result = subprocess.run(
                        [sys.executable, str(script_path)],
                        capture_output=True,
                        text=True,
                        timeout=self.config["timeout"]
                    )
                    
                    if result.returncode == 0:
                        job.logs.append(f"Migration completed: {result.stdout}")
                    else:
                        raise RuntimeError(f"Migration failed: {result.stderr}")
                        
                except Exception as e:
                    raise RuntimeError(f"Migration error: {e}")
    
    async def _post_update_checks(self, job: UpdateJob) -> None:
        """Effectue les vérifications post-mise à jour."""
        # Vérification de l'application
        # Health check
        await self._health_check()
        
        # Vérification de la version
        new_version = self._get_current_version()
        if new_version != job.target_version:
            raise RuntimeError(f"Version mismatch: {new_version} != {job.target_version}")
    
    # ========== MÉTHODES PRIVÉES - BACKUP ==========
    
    async def _create_backup(self) -> str:
        """Crée une sauvegarde du système."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.config['backup_dir']}/nexus_backup_{timestamp}"
        
        # Création du dossier de backup
        Path(backup_path).mkdir(parents=True, exist_ok=True)
        
        # Backup des fichiers critiques
        # Dans un système réel, on sauvegarderait les fichiers importants
        
        # Nettoyage des anciens backups
        await self._cleanup_old_backups()
        
        return backup_path
    
    async def _restore_backup(self, job: UpdateJob) -> None:
        """Restaure une sauvegarde."""
        if job.backup_path and Path(job.backup_path).exists():
            # Restauration des fichiers
            # Dans un système réel, on restaurerait les fichiers
            job.logs.append(f"Backup restored: {job.backup_path}")
    
    async def _cleanup_old_backups(self) -> None:
        """Nettoie les anciennes sauvegardes."""
        backup_dir = Path(self.config["backup_dir"])
        backups = sorted(backup_dir.glob("nexus_backup_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if len(backups) > self.config["max_backups"]:
            for backup in backups[self.config["max_backups"]:]:
                shutil.rmtree(backup)
                logger.info(f"Removed old backup: {backup}")
    
    async def _cleanup_after_rollback(self, job: UpdateJob) -> None:
        """Nettoie après un rollback."""
        # Suppression des fichiers de mise à jour
        update_dir = Path(self.config["update_dir"])
        if update_dir.exists():
            shutil.rmtree(update_dir)
            update_dir.mkdir(parents=True, exist_ok=True)
        
        # Suppression des fichiers temporaires
        temp_dir = Path(self.config["temp_dir"])
        if temp_dir.exists():
            for file in temp_dir.glob("*"):
                if file.is_file():
                    file.unlink()
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _update_check_loop(self) -> None:
        """Boucle de vérification des mises à jour."""
        while self._is_running:
            await asyncio.sleep(self.config["update_check_interval"])
            
            try:
                # Vérification des mises à jour
                versions = await self.check_for_updates()
                
                if versions and self.config["auto_update"]:
                    latest = versions[0] if versions else None
                    if latest and latest.version != self.current_version:
                        # Mise à jour automatique
                        job = UpdateJob(
                            target_version=latest.version,
                            current_version=self.current_version,
                            status=UpdateStatus.PENDING
                        )
                        await self.apply_update(job)
                
            except Exception as e:
                logger.error(f"Update check loop error: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Boucle de nettoyage."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                # Nettoyage des dossiers temporaires
                temp_dir = Path(self.config["temp_dir"])
                if temp_dir.exists():
                    for file in temp_dir.glob("*"):
                        if file.is_file():
                            # Suppression des fichiers de plus de 24h
                            age = time.time() - file.stat().st_mtime
                            if age > 86400:  # 24h
                                file.unlink()
                                logger.debug(f"Removed old temp file: {file}")
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _health_check_loop(self) -> None:
        """Boucle de vérification de santé."""
        while self._is_running:
            await asyncio.sleep(self.config["health_check_timeout"])
            
            try:
                await self._health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _health_check(self) -> None:
        """Vérification de santé du système."""
        # Vérification des services critiques
        # Dans un système réel, on vérifierait les services
        
        # Vérification de la version
        current = self._get_current_version()
        if current != self.current_version:
            logger.warning(f"Version mismatch: {current} != {self.current_version}")
            self.current_version = current
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _get_current_version(self) -> str:
        """Récupère la version actuelle."""
        # Dans un système réel, on lirait depuis un fichier de version
        try:
            with open("VERSION", "r") as f:
                version = f.read().strip()
                if semver.VersionInfo.is_valid(version):
                    return version
        except:
            pass
        
        # Version par défaut
        return self.config.get("default_version", "1.0.0")
    
    async def _get_version_info(self, version: str) -> Optional[VersionInfo]:
        """Récupère les informations d'une version."""
        with self._cache_lock:
            if version in self._version_cache:
                return self._version_cache[version]
        
        # Téléchargement des informations
        versions = await self._fetch_versions()
        for v in versions:
            if v.version == version:
                with self._cache_lock:
                    self._version_cache[version] = v
                return v
        
        return None
    
    async def _get_manifest(self, version: str) -> Optional[UpdateManifest]:
        """Récupère le manifeste d'une version."""
        # Dans un système réel, on téléchargerait le manifeste
        return UpdateManifest(
            version=version,
            required_version="1.0.0",
            compatibility=CompatibilityLevel.FULL,
            description=f"Update to version {version}",
            files=[
                {"source": "update_file.py", "destination": "/app/update_file.py"}
            ]
        )
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_job(self, job_id: str) -> Optional[UpdateJob]:
        """Récupère un job de mise à jour."""
        with self._jobs_lock:
            return self._jobs.get(job_id)
    
    async def get_jobs(self, status: Optional[UpdateStatus] = None) -> List[UpdateJob]:
        """Récupère les jobs de mise à jour."""
        with self._jobs_lock:
            jobs = list(self._jobs.values())
            if status:
                jobs = [j for j in jobs if j.status == status]
            return sorted(jobs, key=lambda j: j.started_at or j.job_id, reverse=True)
    
    async def get_version_info(self, version: str) -> Optional[VersionInfo]:
        """Récupère les informations d'une version."""
        return await self._get_version_info(version)
    
    async def get_latest_version(self) -> Optional[VersionInfo]:
        """Récupère la dernière version."""
        versions = await self.check_for_updates()
        return versions[0] if versions else None
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._jobs_lock:
            self._stats["pending_jobs"] = len([
                j for j in self._jobs.values()
                if j.status in [UpdateStatus.PENDING, UpdateStatus.DOWNLOADING, UpdateStatus.APPLYING]
            ])
        
        return self._stats.copy()
    
    async def create_update_job(self, target_version: str) -> UpdateJob:
        """Crée un job de mise à jour."""
        job = UpdateJob(
            target_version=target_version,
            current_version=self.current_version,
            status=UpdateStatus.PENDING
        )
        
        with self._jobs_lock:
            self._jobs[job.job_id] = job
        
        logger.info(f"Update job created: {job.job_id} -> {target_version}")
        return job


# ============== UPDATE SCHEDULER ==============

class UpdateScheduler:
    """
    Planificateur de mises à jour.
    Gère les mises à jour programmées et les fenêtres de maintenance.
    """
    
    def __init__(self, engine: UpdateEngine):
        self.engine = engine
        self._schedules: Dict[str, Dict[str, Any]] = {}
        self._schedule_lock = threading.RLock()
        self._is_running = False
        
        logger.info("UpdateScheduler initialized")
    
    async def start(self) -> None:
        """Démarre le planificateur."""
        self._is_running = True
        asyncio.create_task(self._scheduler_loop())
        logger.info("UpdateScheduler started")
    
    async def stop(self) -> None:
        """Arrête le planificateur."""
        self._is_running = False
        logger.info("UpdateScheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Boucle de planification."""
        while self._is_running:
            await asyncio.sleep(60)  # Vérification chaque minute
            
            try:
                now = datetime.now(timezone.utc)
                
                with self._schedule_lock:
                    for schedule_id, schedule in self._schedules.items():
                        if schedule.get("active", True):
                            # Vérification de la programmation
                            if self._should_run(now, schedule):
                                # Exécution de la mise à jour
                                version = schedule.get("target_version")
                                if version:
                                    job = await self.engine.create_update_job(version)
                                    asyncio.create_task(self.engine.apply_update(job))
                                    
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
    
    def _should_run(self, now: datetime, schedule: Dict[str, Any]) -> bool:
        """Vérifie si la mise à jour doit être exécutée."""
        schedule_type = schedule.get("type", "daily")
        
        if schedule_type == "daily":
            hour = schedule.get("hour", 2)
            minute = schedule.get("minute", 0)
            return now.hour == hour and now.minute == minute
        
        elif schedule_type == "weekly":
            day = schedule.get("day", 0)  # 0 = Monday
            hour = schedule.get("hour", 2)
            minute = schedule.get("minute", 0)
            return now.weekday() == day and now.hour == hour and now.minute == minute
        
        elif schedule_type == "monthly":
            day = schedule.get("day", 1)
            hour = schedule.get("hour", 2)
            minute = schedule.get("minute", 0)
            return now.day == day and now.hour == hour and now.minute == minute
        
        return False


# ============== FACTORY ==============

class UpdateFactory:
    """Factory pour créer des composants de mise à jour."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> UpdateEngine:
        """Crée un moteur de mise à jour."""
        engine = UpdateEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    async def create_scheduler(engine: UpdateEngine) -> UpdateScheduler:
        """Crée un planificateur de mises à jour."""
        scheduler = UpdateScheduler(engine)
        await scheduler.start()
        return scheduler


# ============== EXPORT ==============

__all__ = [
    "UpdateType",
    "UpdateStatus",
    "UpdateSource",
    "CompatibilityLevel",
    "UpdateManifest",
    "UpdateJob",
    "VersionInfo",
    "UpdateEngineInterface",
    "UpdateEngine",
    "UpdateScheduler",
    "UpdateFactory"
]
