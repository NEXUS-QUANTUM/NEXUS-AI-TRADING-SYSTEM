# trading/bots/hedge_bot/hedge_bot_uninstaller.py
# Advanced Uninstallation & Cleanup System for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Uninstaller Module - Module avancé de désinstallation et nettoyage pour le Hedge Bot.
Assure la désinstallation complète, la suppression sécurisée des données, le nettoyage des ressources
et la restauration de l'état initial du système.
"""

import asyncio
import json
import os
import shutil
import sys
import time
import subprocess
import hashlib
import glob
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
from pathlib import Path
import re

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_uninstaller")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    SecurityContext, DataClass
)


# ============== ENUMS & TYPES ==============

class UninstallMode(Enum):
    """Modes de désinstallation."""
    STANDARD = "standard"          # Désinstallation standard
    COMPLETE = "complete"          # Désinstallation complète
    DATA_ONLY = "data_only"        # Suppression des données uniquement
    CONFIG_ONLY = "config_only"    # Suppression de la configuration uniquement
    LOGS_ONLY = "logs_only"        # Suppression des logs uniquement
    TEMP_ONLY = "temp_only"        # Suppression des fichiers temporaires
    SECURE = "secure"              # Désinstallation sécurisée (plusieurs passes)


class CleanupLevel(Enum):
    """Niveaux de nettoyage."""
    LIGHT = "light"                # Nettoyage léger
    MODERATE = "moderate"          # Nettoyage modéré
    AGGRESSIVE = "aggressive"      # Nettoyage agressif
    THOROUGH = "thorough"          # Nettoyage approfondi
    DEEP = "deep"                  # Nettoyage profond


class DataRemovalMethod(Enum):
    """Méthodes de suppression des données."""
    DELETE = "delete"              # Suppression standard
    SHRED = "shred"                # Suppression sécurisée (shred)
    OVERWRITE = "overwrite"        # Écrasement multiple
    RANDOMIZE = "randomize"        # Remplissage aléatoire
    ZERO = "zero"                  # Écrasement par zéros


# ============== DATA MODELS ==============

@dataclass
class UninstallPlan:
    """Plan de désinstallation."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mode: UninstallMode = UninstallMode.STANDARD
    cleanup_level: CleanupLevel = CleanupLevel.MODERATE
    data_removal_method: DataRemovalMethod = DataRemovalMethod.DELETE
    preserve_paths: List[str] = field(default_factory=list)
    exclude_paths: List[str] = field(default_factory=list)
    include_paths: List[str] = field(default_factory=list)
    backup_before_removal: bool = True
    backup_path: Optional[str] = None
    verify_removal: bool = True
    remove_containers: bool = True
    remove_images: bool = False
    remove_volumes: bool = True
    remove_networks: bool = True
    force: bool = False
    dry_run: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "mode": self.mode.value,
            "cleanup_level": self.cleanup_level.value,
            "data_removal_method": self.data_removal_method.value,
            "preserve_paths": self.preserve_paths,
            "exclude_paths": self.exclude_paths,
            "include_paths": self.include_paths,
            "backup_before_removal": self.backup_before_removal,
            "backup_path": self.backup_path,
            "verify_removal": self.verify_removal,
            "remove_containers": self.remove_containers,
            "remove_images": self.remove_images,
            "remove_volumes": self.remove_volumes,
            "remove_networks": self.remove_networks,
            "force": self.force,
            "dry_run": self.dry_run,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class UninstallResult:
    """Résultat de désinstallation."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    success: bool = False
    files_removed: int = 0
    directories_removed: int = 0
    data_size_removed_mb: float = 0.0
    containers_removed: int = 0
    images_removed: int = 0
    volumes_removed: int = 0
    networks_removed: int = 0
    backup_path: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CleanupOperation:
    """Opération de nettoyage."""
    operation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: str = ""
    operation_type: str = ""  # delete, shred, overwrite, rename, move
    size_bytes: int = 0
    status: str = "pending"  # pending, processing, completed, failed
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class UninstallEngineInterface(ABC):
    """Interface abstraite pour le moteur de désinstallation."""
    
    @abstractmethod
    async def create_plan(self, config: Dict[str, Any]) -> UninstallPlan:
        """Crée un plan de désinstallation."""
        pass
    
    @abstractmethod
    async def execute_plan(self, plan_id: str) -> UninstallResult:
        """Exécute un plan de désinstallation."""
        pass
    
    @abstractmethod
    async def cleanup(self, plan: UninstallPlan) -> UninstallResult:
        """Exécute un nettoyage."""
        pass


# ============== IMPLÉMENTATION ==============

class UninstallEngine(UninstallEngineInterface):
    """
    Moteur de désinstallation avancé pour le Hedge Bot.
    Gère la désinstallation complète, le nettoyage et la suppression sécurisée.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des plans
        self._plans: Dict[str, UninstallPlan] = {}
        self._plans_lock = threading.RLock()
        
        # Gestion des résultats
        self._results: Dict[str, UninstallResult] = {}
        self._results_lock = threading.RLock()
        
        # Opérations en cours
        self._active_operations: Dict[str, CleanupOperation] = {}
        self._ops_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "plans_created": 0,
            "plans_executed": 0,
            "cleanups_performed": 0,
            "files_removed_total": 0,
            "data_removed_mb_total": 0.0,
            "errors_total": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Chemins système à nettoyer
        self._system_paths = self._get_system_paths()
        
        # Exclusions par défaut
        self._default_exclusions = [
            "/bin",
            "/boot",
            "/dev",
            "/etc",
            "/lib",
            "/proc",
            "/sbin",
            "/sys",
            "/usr",
            "/var",
            "/opt",
            "/mnt",
            "/media",
            "/home",
            "/root"
        ]
        
        logger.info("UninstallEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "backup_dir": "./backups",
            "temp_dir": "/tmp/nexus_uninstall",
            "shred_passes": 3,
            "overwrite_pattern": "random",
            "timeout": 3600,
            "verify_removal": True,
            "secure_deletion": True,
            "max_retries": 3,
            "retry_delay": 1.0,
            "docker_timeout": 120,
            "k8s_timeout": 180,
            "remove_configs": True,
            "remove_logs": True,
            "remove_data": True,
            "remove_temp": True,
            "remove_docker": True,
            "remove_k8s": False,
            "preserve_user_data": True
        }
    
    async def start(self) -> None:
        """Démarre le moteur de désinstallation."""
        logger.info("UninstallEngine starting...")
        self._is_running = True
        
        # Création des dossiers
        Path(self.config["backup_dir"]).mkdir(parents=True, exist_ok=True)
        Path(self.config["temp_dir"]).mkdir(parents=True, exist_ok=True)
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._monitor_loop())
        
        logger.info("UninstallEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de désinstallation."""
        logger.info("UninstallEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("UninstallEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_plan(self, config: Dict[str, Any]) -> UninstallPlan:
        """Crée un plan de désinstallation."""
        plan = UninstallPlan(
            mode=UninstallMode(config.get("mode", "standard")),
            cleanup_level=CleanupLevel(config.get("cleanup_level", "moderate")),
            data_removal_method=DataRemovalMethod(config.get("data_removal_method", "delete")),
            preserve_paths=config.get("preserve_paths", []),
            exclude_paths=config.get("exclude_paths", []),
            include_paths=config.get("include_paths", []),
            backup_before_removal=config.get("backup_before_removal", True),
            backup_path=config.get("backup_path"),
            verify_removal=config.get("verify_removal", True),
            remove_containers=config.get("remove_containers", True),
            remove_images=config.get("remove_images", False),
            remove_volumes=config.get("remove_volumes", True),
            remove_networks=config.get("remove_networks", True),
            force=config.get("force", False),
            dry_run=config.get("dry_run", False),
            metadata=config.get("metadata", {})
        )
        
        with self._plans_lock:
            self._plans[plan.plan_id] = plan
            self._stats["plans_created"] += 1
        
        logger.info(f"Uninstall plan created: {plan.plan_id} mode={plan.mode.value}")
        return plan
    
    async def execute_plan(self, plan_id: str) -> UninstallResult:
        """Exécute un plan de désinstallation."""
        with self._plans_lock:
            plan = self._plans.get(plan_id)
            if not plan:
                raise ValueError(f"Plan {plan_id} not found")
        
        logger.info(f"Executing uninstall plan: {plan_id}")
        start_time = datetime.now(timezone.utc)
        
        # Création du résultat
        result = UninstallResult(
            plan_id=plan_id,
            start_time=start_time
        )
        
        try:
            # Sauvegarde préalable
            if plan.backup_before_removal:
                await self._create_backup(plan)
            
            # Nettoyage selon le mode
            if plan.mode == UninstallMode.DATA_ONLY:
                result = await self._cleanup_data(plan)
            elif plan.mode == UninstallMode.CONFIG_ONLY:
                result = await self._cleanup_configs(plan)
            elif plan.mode == UninstallMode.LOGS_ONLY:
                result = await self._cleanup_logs(plan)
            elif plan.mode == UninstallMode.TEMP_ONLY:
                result = await self._cleanup_temp(plan)
            elif plan.mode == UninstallMode.SECURE:
                result = await self._secure_uninstall(plan)
            else:
                result = await self._standard_uninstall(plan)
            
            # Vérification
            if plan.verify_removal:
                await self._verify_removal(plan, result)
            
            result.success = True
            self._stats["plans_executed"] += 1
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            self._stats["errors_total"] += 1
            logger.error(f"Uninstall plan {plan_id} failed: {e}")
        
        finally:
            result.end_time = datetime.now(timezone.utc)
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            
            with self._results_lock:
                self._results[result.result_id] = result
        
        logger.info(f"Uninstall plan {plan_id} completed: success={result.success} "
                   f"duration={result.duration_seconds:.2f}s")
        return result
    
    async def cleanup(self, plan: UninstallPlan) -> UninstallResult:
        """Exécute un nettoyage."""
        return await self.execute_plan(plan.plan_id)
    
    # ========== MÉTHODES PRIVÉES - DÉSINSTALLATION ==========
    
    async def _standard_uninstall(self, plan: UninstallPlan) -> UninstallResult:
        """Désinstallation standard."""
        result = UninstallResult(plan_id=plan.plan_id)
        
        try:
            # 1. Arrêt des services
            await self._stop_services()
            
            # 2. Nettoyage des processus
            await self._cleanup_processes()
            
            # 3. Suppression des fichiers
            file_result = await self._remove_files(plan)
            result.files_removed += file_result["files"]
            result.directories_removed += file_result["dirs"]
            result.data_size_removed_mb += file_result["size_mb"]
            
            # 4. Nettoyage Docker
            if plan.remove_containers:
                docker_result = await self._cleanup_docker(plan)
                result.containers_removed += docker_result["containers"]
                result.images_removed += docker_result["images"]
                result.volumes_removed += docker_result["volumes"]
                result.networks_removed += docker_result["networks"]
            
            # 5. Nettoyage Kubernetes
            if plan.remove_k8s:
                k8s_result = await self._cleanup_kubernetes(plan)
                result.metadata["k8s"] = k8s_result
            
            # 6. Suppression des configurations
            if self.config["remove_configs"]:
                await self._remove_configs()
            
            # 7. Suppression des logs
            if self.config["remove_logs"]:
                await self._remove_logs()
            
            # 8. Suppression des données
            if self.config["remove_data"]:
                await self._remove_data()
            
            # 9. Suppression des fichiers temporaires
            if self.config["remove_temp"]:
                await self._remove_temp()
            
            return result
            
        except Exception as e:
            result.errors.append(str(e))
            raise
    
    async def _cleanup_data(self, plan: UninstallPlan) -> UninstallResult:
        """Nettoyage des données uniquement."""
        result = UninstallResult(plan_id=plan.plan_id)
        
        try:
            # Suppression des données utilisateur
            data_paths = self._get_data_paths()
            for path in data_paths:
                if Path(path).exists():
                    await self._remove_path(path, plan)
                    result.files_removed += 1
            
            return result
            
        except Exception as e:
            result.errors.append(str(e))
            raise
    
    async def _cleanup_configs(self, plan: UninstallPlan) -> UninstallResult:
        """Nettoyage des configurations."""
        result = UninstallResult(plan_id=plan.plan_id)
        
        try:
            # Suppression des fichiers de configuration
            config_paths = self._get_config_paths()
            for path in config_paths:
                if Path(path).exists():
                    await self._remove_path(path, plan)
                    result.files_removed += 1
            
            return result
            
        except Exception as e:
            result.errors.append(str(e))
            raise
    
    async def _cleanup_logs(self, plan: UninstallPlan) -> UninstallResult:
        """Nettoyage des logs."""
        result = UninstallResult(plan_id=plan.plan_id)
        
        try:
            # Suppression des logs
            log_paths = self._get_log_paths()
            for path in log_paths:
                if Path(path).exists():
                    await self._remove_path(path, plan)
                    result.files_removed += 1
            
            return result
            
        except Exception as e:
            result.errors.append(str(e))
            raise
    
    async def _cleanup_temp(self, plan: UninstallPlan) -> UninstallResult:
        """Nettoyage des fichiers temporaires."""
        result = UninstallResult(plan_id=plan.plan_id)
        
        try:
            # Suppression des fichiers temporaires
            temp_paths = self._get_temp_paths()
            for path in temp_paths:
                if Path(path).exists():
                    await self._remove_path(path, plan)
                    result.files_removed += 1
            
            return result
            
        except Exception as e:
            result.errors.append(str(e))
            raise
    
    async def _secure_uninstall(self, plan: UninstallPlan) -> UninstallResult:
        """Désinstallation sécurisée."""
        result = UninstallResult(plan_id=plan.plan_id)
        
        try:
            # Plusieurs passes de nettoyage
            passes = 3
            for i in range(passes):
                logger.info(f"Secure uninstall pass {i+1}/{passes}")
                
                # Utilisation de la méthode de suppression sécurisée
                plan.data_removal_method = DataRemovalMethod.SHRED
                
                # Exécution du nettoyage
                pass_result = await self._standard_uninstall(plan)
                
                result.files_removed += pass_result.files_removed
                result.directories_removed += pass_result.directories_removed
                result.data_size_removed_mb += pass_result.data_size_removed_mb
            
            return result
            
        except Exception as e:
            result.errors.append(str(e))
            raise
    
    # ========== MÉTHODES PRIVÉES - SUPPRESSION ==========
    
    async def _remove_files(self, plan: UninstallPlan) -> Dict[str, Any]:
        """Supprime les fichiers."""
        result = {
            "files": 0,
            "dirs": 0,
            "size_mb": 0.0
        }
        
        # Chemins à supprimer
        paths = self._get_uninstall_paths()
        
        # Filtrage
        if plan.include_paths:
            paths = [p for p in paths if any(p.startswith(inc) for inc in plan.include_paths)]
        
        if plan.exclude_paths:
            paths = [p for p in paths if not any(p.startswith(exc) for exc in plan.exclude_paths)]
        
        for path in paths:
            if not Path(path).exists():
                continue
            
            # Vérification des exclusions système
            if self._is_system_path(path):
                if not plan.force:
                    continue
            
            # Vérification des préservations
            if any(path.startswith(pres) for pres in plan.preserve_paths):
                continue
            
            # Suppression
            try:
                size = await self._remove_path(path, plan)
                result["size_mb"] += size / (1024 * 1024)
                result["files"] += 1
                
            except Exception as e:
                if plan.force:
                    logger.warning(f"Force removing {path}: {e}")
                    try:
                        await self._force_remove(path)
                        result["files"] += 1
                    except Exception as e2:
                        logger.error(f"Force remove failed {path}: {e2}")
                else:
                    raise
        
        return result
    
    async def _remove_path(self, path: str, plan: UninstallPlan) -> int:
        """Supprime un chemin."""
        path_obj = Path(path)
        
        if not path_obj.exists():
            return 0
        
        size = 0
        
        if plan.dry_run:
            logger.info(f"DRY RUN: Would remove {path}")
            return 0
        
        # Méthode de suppression
        if plan.data_removal_method == DataRemovalMethod.SHRED:
            size = await self._shred_path(path)
        elif plan.data_removal_method == DataRemovalMethod.OVERWRITE:
            size = await self._overwrite_path(path)
        elif plan.data_removal_method == DataRemovalMethod.RANDOMIZE:
            size = await self._randomize_path(path)
        elif plan.data_removal_method == DataRemovalMethod.ZERO:
            size = await self._zero_path(path)
        else:
            # Suppression standard
            if path_obj.is_file():
                size = path_obj.stat().st_size
                path_obj.unlink()
            elif path_obj.is_dir():
                # Calcul de la taille
                for root, dirs, files in os.walk(path):
                    for file in files:
                        file_path = Path(root) / file
                        size += file_path.stat().st_size
                shutil.rmtree(path)
        
        return size
    
    async def _shred_path(self, path: str) -> int:
        """Supprime sécurisée avec shred."""
        path_obj = Path(path)
        size = 0
        
        if path_obj.is_file():
            size = path_obj.stat().st_size
            # Utilisation de shred
            passes = self.config["shred_passes"]
            subprocess.run(
                ["shred", "-f", "-n", str(passes), "-z", str(path)],
                check=False,
                capture_output=True
            )
            path_obj.unlink()
        elif path_obj.is_dir():
            # Shred récursif
            for root, dirs, files in os.walk(path, topdown=False):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.is_file():
                        size += file_path.stat().st_size
                        subprocess.run(
                            ["shred", "-f", "-n", "3", "-z", str(file_path)],
                            check=False,
                            capture_output=True
                        )
                        file_path.unlink()
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    try:
                        dir_path.rmdir()
                    except:
                        shutil.rmtree(dir_path, ignore_errors=True)
            shutil.rmtree(path, ignore_errors=True)
        
        return size
    
    async def _overwrite_path(self, path: str) -> int:
        """Écrase le contenu avant suppression."""
        path_obj = Path(path)
        size = 0
        
        if path_obj.is_file():
            size = path_obj.stat().st_size
            # Écriture de données aléatoires
            with open(path_obj, 'wb') as f:
                for _ in range(3):
                    f.write(os.urandom(size))
                    f.seek(0)
            path_obj.unlink()
        elif path_obj.is_dir():
            for root, dirs, files in os.walk(path, topdown=False):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.is_file():
                        size += file_path.stat().st_size
                        with open(file_path, 'wb') as f:
                            f.write(os.urandom(size))
                        file_path.unlink()
            shutil.rmtree(path, ignore_errors=True)
        
        return size
    
    async def _randomize_path(self, path: str) -> int:
        """Remplit avec des données aléatoires."""
        path_obj = Path(path)
        size = 0
        
        if path_obj.is_file():
            size = path_obj.stat().st_size
            # Remplissage aléatoire
            with open(path_obj, 'wb') as f:
                f.write(os.urandom(size))
            path_obj.unlink()
        elif path_obj.is_dir():
            for root, dirs, files in os.walk(path, topdown=False):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.is_file():
                        size += file_path.stat().st_size
                        with open(file_path, 'wb') as f:
                            f.write(os.urandom(size))
                        file_path.unlink()
            shutil.rmtree(path, ignore_errors=True)
        
        return size
    
    async def _zero_path(self, path: str) -> int:
        """Écrit des zéros avant suppression."""
        path_obj = Path(path)
        size = 0
        
        if path_obj.is_file():
            size = path_obj.stat().st_size
            # Écriture de zéros
            with open(path_obj, 'wb') as f:
                f.write(b'\x00' * size)
            path_obj.unlink()
        elif path_obj.is_dir():
            for root, dirs, files in os.walk(path, topdown=False):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.is_file():
                        size += file_path.stat().st_size
                        with open(file_path, 'wb') as f:
                            f.write(b'\x00' * size)
                        file_path.unlink()
            shutil.rmtree(path, ignore_errors=True)
        
        return size
    
    async def _force_remove(self, path: str) -> None:
        """Suppression forcée."""
        try:
            if Path(path).is_file():
                Path(path).unlink()
            elif Path(path).is_dir():
                shutil.rmtree(path, ignore_errors=True)
        except Exception as e:
            # Utilisation de subprocess en dernier recours
            subprocess.run(["rm", "-rf", path], check=False)
    
    # ========== MÉTHODES PRIVÉES - NETTOYAGE ==========
    
    async def _cleanup_docker(self, plan: UninstallPlan) -> Dict[str, int]:
        """Nettoie les ressources Docker."""
        result = {
            "containers": 0,
            "images": 0,
            "volumes": 0,
            "networks": 0
        }
        
        try:
            # Vérification de Docker
            try:
                subprocess.run(["docker", "version"], check=False, capture_output=True)
            except:
                logger.warning("Docker not available")
                return result
            
            if plan.dry_run:
                logger.info("DRY RUN: Would remove Docker resources")
                return result
            
            # Suppression des conteneurs
            if plan.remove_containers:
                # Conteneurs Nexus
                containers = subprocess.check_output(
                    ["docker", "ps", "-a", "--filter", "name=nexus*", "-q"]
                ).decode().strip().split()
                
                for container in containers:
                    subprocess.run(["docker", "rm", "-f", container], check=False)
                    result["containers"] += 1
            
            # Suppression des images
            if plan.remove_images:
                images = subprocess.check_output(
                    ["docker", "images", "--filter", "reference=nexus*", "-q"]
                ).decode().strip().split()
                
                for image in images:
                    subprocess.run(["docker", "rmi", "-f", image], check=False)
                    result["images"] += 1
            
            # Suppression des volumes
            if plan.remove_volumes:
                volumes = subprocess.check_output(
                    ["docker", "volume", "ls", "--filter", "name=nexus*", "-q"]
                ).decode().strip().split()
                
                for volume in volumes:
                    subprocess.run(["docker", "volume", "rm", "-f", volume], check=False)
                    result["volumes"] += 1
            
            # Suppression des réseaux
            if plan.remove_networks:
                networks = subprocess.check_output(
                    ["docker", "network", "ls", "--filter", "name=nexus*", "-q"]
                ).decode().strip().split()
                
                for network in networks:
                    subprocess.run(["docker", "network", "rm", network], check=False)
                    result["networks"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Docker cleanup error: {e}")
            return result
    
    async def _cleanup_kubernetes(self, plan: UninstallPlan) -> Dict[str, Any]:
        """Nettoie les ressources Kubernetes."""
        result = {
            "deployments": 0,
            "services": 0,
            "configmaps": 0,
            "secrets": 0,
            "pods": 0
        }
        
        try:
            # Vérification de kubectl
            try:
                subprocess.run(["kubectl", "version"], check=False, capture_output=True)
            except:
                logger.warning("kubectl not available")
                return result
            
            if plan.dry_run:
                logger.info("DRY RUN: Would remove Kubernetes resources")
                return result
            
            # Suppression des ressources Nexus
            # Déploiements
            deployments = subprocess.check_output(
                ["kubectl", "get", "deployments", "-l", "app=nexus", "-o", "name"]
            ).decode().strip().split()
            
            for deployment in deployments:
                subprocess.run(["kubectl", "delete", deployment], check=False)
                result["deployments"] += 1
            
            # Services
            services = subprocess.check_output(
                ["kubectl", "get", "services", "-l", "app=nexus", "-o", "name"]
            ).decode().strip().split()
            
            for service in services:
                subprocess.run(["kubectl", "delete", service], check=False)
                result["services"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Kubernetes cleanup error: {e}")
            return result
    
    async def _stop_services(self) -> None:
        """Arrête les services Nexus."""
        try:
            # Arrêt des services systemd
            services = subprocess.check_output(
                ["systemctl", "list-units", "--all", "nexus*", "--no-legend"]
            ).decode().strip().split()
            
            for service in services:
                if service:
                    subprocess.run(["systemctl", "stop", service], check=False)
            
            # Arrêt des processus
            subprocess.run(["pkill", "-f", "nexus"], check=False)
            
        except Exception as e:
            logger.warning(f"Stop services error: {e}")
    
    async def _cleanup_processes(self) -> None:
        """Nettoie les processus Nexus."""
        try:
            # Terminaison des processus
            subprocess.run(["pkill", "-9", "-f", "nexus"], check=False)
            
            # Attente de la terminaison
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.warning(f"Cleanup processes error: {e}")
    
    # ========== MÉTHODES PRIVÉES - VÉRIFICATION ==========
    
    async def _verify_removal(self, plan: UninstallPlan, result: UninstallResult) -> None:
        """Vérifie la suppression."""
        # Vérification des chemins
        paths = self._get_uninstall_paths()
        
        remaining = []
        for path in paths:
            if Path(path).exists():
                remaining.append(path)
        
        if remaining:
            result.warnings.append(f"Some paths still exist: {remaining}")
            logger.warning(f"Remaining paths: {remaining}")
        
        # Vérification des processus
        try:
            processes = subprocess.check_output(
                ["ps", "aux", "|", "grep", "nexus", "|", "grep", "-v", "grep"]
            ).decode().strip()
            
            if processes:
                result.warnings.append("Some processes still running")
        except:
            pass
    
    # ========== MÉTHODES PRIVÉES - SAUVEGARDE ==========
    
    async def _create_backup(self, plan: UninstallPlan) -> None:
        """Crée une sauvegarde avant suppression."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = plan.backup_path or f"{self.config['backup_dir']}/nexus_backup_{timestamp}"
        
        # Création du dossier de backup
        Path(backup_path).mkdir(parents=True, exist_ok=True)
        
        # Sauvegarde des fichiers importants
        paths_to_backup = [
            "./config",
            "./data",
            "./logs",
            "./models",
            "./.env",
            "./VERSION"
        ]
        
        for path in paths_to_backup:
            if Path(path).exists():
                dest = Path(backup_path) / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                if Path(path).is_file():
                    shutil.copy2(path, dest)
                elif Path(path).is_dir():
                    shutil.copytree(path, dest, dirs_exist_ok=True)
        
        logger.info(f"Backup created at {backup_path}")
        plan.backup_path = backup_path
    
    # ========== MÉTHODES PRIVÉES - CHEMINS ==========
    
    def _get_uninstall_paths(self) -> List[str]:
        """Récupère les chemins à désinstaller."""
        paths = [
            "./config",
            "./data",
            "./logs",
            "./models",
            "./.env",
            "./VERSION",
            "./.nexus",
            "./nexus.db",
            "./venv",
            "./.venv",
            "./__pycache__",
            "*.pyc",
            "*.pyo",
            ".pytest_cache",
            ".coverage",
            "htmlcov",
            "dist",
            "build",
            "*.egg-info",
            "*.egg"
        ]
        return paths
    
    def _get_data_paths(self) -> List[str]:
        """Récupère les chemins de données."""
        return [
            "./data",
            "./models",
            "./nexus.db",
            "./*.db",
            "./*.sqlite"
        ]
    
    def _get_config_paths(self) -> List[str]:
        """Récupère les chemins de configuration."""
        return [
            "./config",
            "./.env",
            "./VERSION",
            "./*.yaml",
            "./*.yml",
            "./*.json",
            "./*.toml",
            "./*.cfg"
        ]
    
    def _get_log_paths(self) -> List[str]:
        """Récupère les chemins de logs."""
        return [
            "./logs",
            "./*.log",
            "./*.log.*",
            "./*.out",
            "./*.err"
        ]
    
    def _get_temp_paths(self) -> List[str]:
        """Récupère les chemins temporaires."""
        return [
            "./__pycache__",
            "./.pytest_cache",
            "./.cache",
            "./tmp",
            "./temp",
            "./*.tmp",
            "./*.temp"
        ]
    
    def _get_system_paths(self) -> List[str]:
        """Récupère les chemins système."""
        return self._default_exclusions.copy()
    
    def _is_system_path(self, path: str) -> bool:
        """Vérifie si un chemin est système."""
        for sys_path in self._system_paths:
            if path.startswith(sys_path):
                return True
        return False
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cleanup_loop(self) -> None:
        """Boucle de nettoyage automatique."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                # Nettoyage des fichiers temporaires anciens
                temp_dir = Path(self.config["temp_dir"])
                if temp_dir.exists():
                    now = datetime.now(timezone.utc)
                    for item in temp_dir.iterdir():
                        if item.is_file():
                            mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
                            age = (now - mtime).total_seconds()
                            if age > 86400:  # 24 heures
                                item.unlink()
                                logger.debug(f"Removed old temp file: {item}")
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _monitor_loop(self) -> None:
        """Boucle de monitoring."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                # Vérification des opérations en cours
                with self._ops_lock:
                    stale_ops = [
                        oid for oid, op in self._active_operations.items()
                        if op.status == "processing"
                        and (datetime.now(timezone.utc) - op.timestamp).total_seconds() > self.config["timeout"]
                    ]
                    
                    for oid in stale_ops:
                        logger.warning(f"Stale operation detected: {oid}")
                        self._active_operations[oid].status = "failed"
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_plan(self, plan_id: str) -> Optional[UninstallPlan]:
        """Récupère un plan de désinstallation."""
        with self._plans_lock:
            return self._plans.get(plan_id)
    
    async def get_plans(self) -> List[UninstallPlan]:
        """Récupère les plans de désinstallation."""
        with self._plans_lock:
            return list(self._plans.values())
    
    async def get_result(self, result_id: str) -> Optional[UninstallResult]:
        """Récupère un résultat de désinstallation."""
        with self._results_lock:
            return self._results.get(result_id)
    
    async def get_results(self, limit: int = 100) -> List[UninstallResult]:
        """Récupère les résultats de désinstallation."""
        with self._results_lock:
            results = list(self._results.values())
            return sorted(results, key=lambda r: r.start_time, reverse=True)[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._plans_lock:
            self._stats["total_plans"] = len(self._plans)
        with self._results_lock:
            self._stats["total_results"] = len(self._results)
        
        return self._stats.copy()


# ============== FACTORY ==============

class UninstallFactory:
    """Factory pour créer des composants de désinstallation."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> UninstallEngine:
        """Crée un moteur de désinstallation."""
        engine = UninstallEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "UninstallMode",
    "CleanupLevel",
    "DataRemovalMethod",
    "UninstallPlan",
    "UninstallResult",
    "CleanupOperation",
    "UninstallEngineInterface",
    "UninstallEngine",
    "UninstallFactory"
]
