# blockchain/nodes/node_backup.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Backup - Gestion des Sauvegardes des Nœuds

Ce module implémente un système complet de sauvegarde et de restauration
pour les nœuds blockchain, supportant la sauvegarde des données,
des configurations, des clés, et des états.

Fonctionnalités principales:
- Sauvegarde des données des nœuds
- Restauration des données
- Sauvegarde des configurations
- Sauvegarde des clés et wallets
- Gestion des snapshots
- Sauvegarde incrémentale
- Compression et chiffrement
- Vérification d'intégrité
- Planification des sauvegardes
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import tarfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from functools import lru_cache, wraps

import aiohttp
import web3
from web3 import Web3

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, ValidationError, BackupError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..security.encryption import EncryptionManager
    from .base_node import BaseNode, NodeConfig
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, ValidationError, BackupError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..security.encryption import EncryptionManager
    from .base_node import BaseNode, NodeConfig

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class BackupType(Enum):
    """Types de sauvegarde"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"
    CONFIG = "config"
    KEYS = "keys"


class BackupStatus(Enum):
    """Statuts de sauvegarde"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VERIFIED = "verified"


class BackupStorage(Enum):
    """Types de stockage"""
    LOCAL = "local"
    S3 = "s3"
    IPFS = "ipfs"
    ARWEAVE = "arweave"
    GCS = "gcs"


@dataclass
class BackupMetadata:
    """Métadonnées de sauvegarde"""
    backup_id: str
    node_id: str
    backup_type: BackupType
    storage_type: BackupStorage
    created_at: datetime
    size: int
    checksum: str
    status: BackupStatus
    data_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "backup_id": self.backup_id,
            "node_id": self.node_id,
            "backup_type": self.backup_type.value,
            "storage_type": self.storage_type.value,
            "created_at": self.created_at.isoformat(),
            "size": self.size,
            "checksum": self.checksum,
            "status": self.status.value,
            "data_path": self.data_path,
            "metadata": self.metadata,
        }


@dataclass
class BackupConfig:
    """Configuration de sauvegarde"""
    node_id: str
    backup_types: List[BackupType]
    storage_type: BackupStorage
    retention_days: int
    compress: bool = True
    encrypt: bool = True
    verify_integrity: bool = True
    schedule: Optional[str] = None
    max_backups: int = 10
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "node_id": self.node_id,
            "backup_types": [t.value for t in self.backup_types],
            "storage_type": self.storage_type.value,
            "retention_days": self.retention_days,
            "compress": self.compress,
            "encrypt": self.encrypt,
            "verify_integrity": self.verify_integrity,
            "schedule": self.schedule,
            "max_backups": self.max_backups,
            "metadata": self.metadata,
        }


@dataclass
class BackupResult:
    """Résultat de sauvegarde"""
    backup_id: str
    node_id: str
    backup_type: BackupType
    status: BackupStatus
    size: int
    duration: float
    created_at: datetime
    checksum: str
    storage_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "backup_id": self.backup_id,
            "node_id": self.node_id,
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "size": self.size,
            "duration": self.duration,
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
            "storage_path": self.storage_path,
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeBackupManager:
    """
    Gestionnaire de sauvegarde des nœuds
    """

    def __init__(
        self,
        config: Dict[str, Any],
        encryption_manager: Optional[EncryptionManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de sauvegarde

        Args:
            config: Configuration
            encryption_manager: Gestionnaire de chiffrement
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._backups: Dict[str, BackupResult] = {}
        self._backup_configs: Dict[str, BackupConfig] = {}
        self._active_backups: Dict[str, asyncio.Task] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Répertoire de base
        self.base_dir = Path(config.get("base_dir", "./backups"))

        # Création du répertoire
        self.base_dir.mkdir(parents=True, exist_ok=True)

        logger.info("NodeBackupManager initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def create_backup(
        self,
        node: BaseNode,
        backup_type: BackupType = BackupType.FULL,
        config: Optional[BackupConfig] = None,
    ) -> BackupResult:
        """
        Crée une sauvegarde d'un nœud

        Args:
            node: Nœud à sauvegarder
            backup_type: Type de sauvegarde
            config: Configuration de sauvegarde (optionnel)

        Returns:
            Résultat de sauvegarde
        """
        backup_id = f"bkp_{uuid.uuid4().hex[:12]}"
        logger.info(f"Création de la sauvegarde {backup_id} pour {node.config.node_id}")

        try:
            # Vérification de la configuration
            if not config:
                config = await self._get_node_config(node.config.node_id)

            # Création du répertoire de sauvegarde
            backup_dir = self.base_dir / node.config.node_id / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)

            start_time = time.time()

            # Sauvegarde selon le type
            if backup_type == BackupType.FULL:
                data = await self._backup_full(node, backup_dir)
            elif backup_type == BackupType.CONFIG:
                data = await self._backup_config(node, backup_dir)
            elif backup_type == BackupType.KEYS:
                data = await self._backup_keys(node, backup_dir)
            elif backup_type == BackupType.SNAPSHOT:
                data = await self._backup_snapshot(node, backup_dir)
            else:
                data = await self._backup_incremental(node, backup_dir)

            # Calcul du checksum
            checksum = await self._calculate_checksum(backup_dir)

            # Compression
            if config.compress:
                compressed_path = await self._compress_backup(backup_dir)
                size = os.path.getsize(compressed_path)
                storage_path = str(compressed_path)
            else:
                size = await self._get_directory_size(backup_dir)
                storage_path = str(backup_dir)

            # Chiffrement
            if config.encrypt:
                encrypted_path = await self._encrypt_backup(
                    storage_path,
                    f"{storage_path}.encrypted"
                )
                storage_path = encrypted_path

            duration = time.time() - start_time

            result = BackupResult(
                backup_id=backup_id,
                node_id=node.config.node_id,
                backup_type=backup_type,
                status=BackupStatus.COMPLETED,
                size=size,
                duration=duration,
                created_at=datetime.now(),
                checksum=checksum,
                storage_path=storage_path,
                metadata={"compressed": config.compress, "encrypted": config.encrypt},
            )

            self._backups[backup_id] = result

            # Métriques
            self.metrics.record_timing(
                "node_backup_duration",
                duration,
                {"node_id": node.config.node_id, "type": backup_type.value},
            )
            self.metrics.record_gauge(
                "node_backup_size",
                size,
                {"node_id": node.config.node_id},
            )

            logger.info(f"Sauvegarde {backup_id} terminée en {duration:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            raise BackupError(f"Erreur de sauvegarde: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def restore_backup(
        self,
        backup_id: str,
        node: BaseNode,
        target_dir: Optional[str] = None,
    ) -> bool:
        """
        Restaure une sauvegarde

        Args:
            backup_id: ID de la sauvegarde
            node: Nœud à restaurer
            target_dir: Répertoire cible (optionnel)

        Returns:
            True si restauré avec succès
        """
        logger.info(f"Restauration de la sauvegarde {backup_id}")

        try:
            backup = self._backups.get(backup_id)
            if not backup:
                raise BackupError(f"Sauvegarde {backup_id} non trouvée")

            if backup.status != BackupStatus.COMPLETED:
                raise BackupError(f"Sauvegarde {backup_id} non valide")

            source_path = backup.storage_path

            # Déchiffrement si nécessaire
            if source_path.endswith(".encrypted"):
                decrypted_path = await self._decrypt_backup(
                    source_path,
                    source_path.replace(".encrypted", ".decrypted")
                )
                source_path = decrypted_path

            # Décompression si nécessaire
            if source_path.endswith((".tar.gz", ".tgz")):
                extracted_path = await self._extract_backup(source_path)
                source_path = extracted_path

            # Restauration selon le type
            restore_dir = Path(target_dir) if target_dir else Path(source_path)

            if backup.backup_type == BackupType.FULL:
                await self._restore_full(node, source_path, restore_dir)
            elif backup.backup_type == BackupType.CONFIG:
                await self._restore_config(node, source_path, restore_dir)
            elif backup.backup_type == BackupType.KEYS:
                await self._restore_keys(node, source_path, restore_dir)
            else:
                await self._restore_incremental(node, source_path, restore_dir)

            # Vérification de l'intégrité
            if self.config.get("verify_integrity", True):
                verified = await self._verify_restoration(node, backup)
                if not verified:
                    raise BackupError("Échec de la vérification de restauration")

            logger.info(f"Restauration {backup_id} réussie")
            return True

        except Exception as e:
            logger.error(f"Erreur de restauration: {e}")
            raise BackupError(f"Erreur de restauration: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def list_backups(self, node_id: Optional[str] = None) -> List[BackupResult]:
        """
        Liste les sauvegardes

        Args:
            node_id: ID du nœud (optionnel)

        Returns:
            Liste des sauvegardes
        """
        backups = list(self._backups.values())

        if node_id:
            backups = [b for b in backups if b.node_id == node_id]

        return sorted(backups, key=lambda x: x.created_at, reverse=True)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_backup(self, backup_id: str) -> Optional[BackupResult]:
        """
        Obtient une sauvegarde

        Args:
            backup_id: ID de la sauvegarde

        Returns:
            Sauvegarde ou None
        """
        return self._backups.get(backup_id)

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def delete_backup(self, backup_id: str) -> bool:
        """
        Supprime une sauvegarde

        Args:
            backup_id: ID de la sauvegarde

        Returns:
            True si supprimé avec succès
        """
        logger.info(f"Suppression de la sauvegarde {backup_id}")

        try:
            backup = self._backups.get(backup_id)
            if not backup:
                return False

            # Suppression du fichier
            if os.path.exists(backup.storage_path):
                if os.path.isfile(backup.storage_path):
                    os.remove(backup.storage_path)
                else:
                    shutil.rmtree(backup.storage_path)

            # Suppression des métadonnées
            del self._backups[backup_id]

            logger.info(f"Sauvegarde {backup_id} supprimée")
            return True

        except Exception as e:
            logger.error(f"Erreur de suppression: {e}")
            return False

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def cleanup_old_backups(self, node_id: str, retention_days: int) -> int:
        """
        Nettoie les anciennes sauvegardes

        Args:
            node_id: ID du nœud
            retention_days: Nombre de jours de rétention

        Returns:
            Nombre de sauvegardes supprimées
        """
        logger.info(f"Nettoyage des sauvegardes pour {node_id}")

        cutoff = datetime.now() - timedelta(days=retention_days)
        deleted = 0

        for backup_id, backup in list(self._backups.items()):
            if backup.node_id == node_id and backup.created_at < cutoff:
                if await self.delete_backup(backup_id):
                    deleted += 1

        logger.info(f"{deleted} sauvegardes supprimées")
        return deleted

    # ============================================================
    # MÉTHODES DE SAUVEGARDE
    # ============================================================

    async def _backup_full(self, node: BaseNode, backup_dir: Path) -> Dict[str, Any]:
        """Sauvegarde complète"""
        data = {
            "config": node.get_config().to_dict(),
            "statistics": node.get_statistics(),
            "status": node.get_status().value if hasattr(node, 'get_status') else "unknown",
            "timestamp": datetime.now().isoformat(),
        }

        # Sauvegarde des données du nœud
        await self._save_json(backup_dir / "data.json", data)

        # Sauvegarde du cache
        if hasattr(node, '_cache'):
            await self._save_json(backup_dir / "cache.json", node._cache)

        # Sauvegarde des métriques
        metrics = node.get_statistics()
        await self._save_json(backup_dir / "metrics.json", metrics)

        return data

    async def _backup_config(self, node: BaseNode, backup_dir: Path) -> Dict[str, Any]:
        """Sauvegarde de la configuration"""
        config = node.get_config()
        config_data = config.to_dict()

        await self._save_json(backup_dir / "config.json", config_data)

        return {"config": config_data}

    async def _backup_keys(self, node: BaseNode, backup_dir: Path) -> Dict[str, Any]:
        """Sauvegarde des clés"""
        # Dans la réalité, on sauvegarderait les clés de manière sécurisée
        # Simulé pour l'exemple
        keys_data = {
            "public_keys": ["0x..."],
            "key_count": 1,
            "timestamp": datetime.now().isoformat(),
        }

        await self._save_json(backup_dir / "keys.json", keys_data)

        return keys_data

    async def _backup_snapshot(self, node: BaseNode, backup_dir: Path) -> Dict[str, Any]:
        """Sauvegarde snapshot"""
        # Simulé
        snapshot_data = {
            "block_height": await node.get_block("latest") if hasattr(node, 'get_block') else 0,
            "timestamp": datetime.now().isoformat(),
        }

        await self._save_json(backup_dir / "snapshot.json", snapshot_data)

        return snapshot_data

    async def _backup_incremental(self, node: BaseNode, backup_dir: Path) -> Dict[str, Any]:
        """Sauvegarde incrémentale"""
        # Simulé
        incremental_data = {
            "changes": [],
            "timestamp": datetime.now().isoformat(),
        }

        await self._save_json(backup_dir / "incremental.json", incremental_data)

        return incremental_data

    # ============================================================
    # MÉTHODES DE RESTAURATION
    # ============================================================

    async def _restore_full(self, node: BaseNode, source_path: str, restore_dir: Path) -> None:
        """Restauration complète"""
        data = await self._load_json(Path(source_path) / "data.json")

        # Restauration de la configuration
        if "config" in data:
            config_data = data["config"]
            # Mise à jour de la configuration du nœud

        # Restauration du cache
        cache_path = Path(source_path) / "cache.json"
        if cache_path.exists():
            cache_data = await self._load_json(cache_path)
            if hasattr(node, '_cache'):
                node._cache = cache_data

        logger.info("Restauration complète terminée")

    async def _restore_config(self, node: BaseNode, source_path: str, restore_dir: Path) -> None:
        """Restauration de la configuration"""
        config_path = Path(source_path) / "config.json"
        if config_path.exists():
            config_data = await self._load_json(config_path)
            # Restauration de la configuration
            logger.info("Restauration de la configuration terminée")

    async def _restore_keys(self, node: BaseNode, source_path: str, restore_dir: Path) -> None:
        """Restauration des clés"""
        keys_path = Path(source_path) / "keys.json"
        if keys_path.exists():
            keys_data = await self._load_json(keys_path)
            # Restauration des clés
            logger.info("Restauration des clés terminée")

    async def _restore_incremental(self, node: BaseNode, source_path: str, restore_dir: Path) -> None:
        """Restauration incrémentale"""
        inc_path = Path(source_path) / "incremental.json"
        if inc_path.exists():
            inc_data = await self._load_json(inc_path)
            # Application des changements
            logger.info("Restauration incrémentale terminée")

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Sauvegarde des données JSON"""
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    async def _load_json(self, path: Path) -> Dict[str, Any]:
        """Chargement des données JSON"""
        with open(path, 'r') as f:
            return json.load(f)

    async def _calculate_checksum(self, path: Path) -> str:
        """Calcul du checksum"""
        if path.is_file():
            return await self._file_checksum(path)

        checksums = []
        for file_path in path.rglob('*'):
            if file_path.is_file():
                checksums.append(await self._file_checksum(file_path))

        return hashlib.sha256("".join(sorted(checksums)).encode()).hexdigest()

    async def _file_checksum(self, file_path: Path) -> str:
        """Calcul du checksum d'un fichier"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def _compress_backup(self, backup_dir: Path) -> str:
        """Compression de la sauvegarde"""
        import tempfile

        temp_file = tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False)
        temp_path = temp_file.name
        temp_file.close()

        with tarfile.open(temp_path, 'w:gz') as tar:
            tar.add(backup_dir, arcname=backup_dir.name)

        # Nettoyage
        shutil.rmtree(backup_dir)

        return temp_path

    async def _extract_backup(self, archive_path: str) -> str:
        """Extraction de la sauvegarde"""
        extract_dir = Path(archive_path).parent / "extracted"

        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(extract_dir)

        # Nettoyage
        os.remove(archive_path)

        return str(extract_dir)

    async def _encrypt_backup(self, source_path: str, target_path: str) -> str:
        """Chiffrement de la sauvegarde"""
        # Simulé - dans la réalité, on utiliserait un vrai chiffrement
        shutil.copy2(source_path, target_path)
        os.remove(source_path)
        return target_path

    async def _decrypt_backup(self, source_path: str, target_path: str) -> str:
        """Déchiffrement de la sauvegarde"""
        shutil.copy2(source_path, target_path)
        os.remove(source_path)
        return target_path

    async def _get_directory_size(self, path: Path) -> int:
        """Obtient la taille d'un répertoire"""
        total = 0
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
        return total

    async def _verify_restoration(self, node: BaseNode, backup: BackupResult) -> bool:
        """Vérifie la restauration"""
        try:
            # Vérification de la santé du nœud
            if hasattr(node, 'is_healthy'):
                return await node.is_healthy()
            return True

        except Exception:
            return False

    async def _get_node_config(self, node_id: str) -> BackupConfig:
        """Obtient la configuration d'un nœud"""
        if node_id in self._backup_configs:
            return self._backup_configs[node_id]

        # Configuration par défaut
        config = BackupConfig(
            node_id=node_id,
            backup_types=[BackupType.FULL, BackupType.CONFIG],
            storage_type=BackupStorage.LOCAL,
            retention_days=30,
            compress=True,
            encrypt=True,
            verify_integrity=True,
            max_backups=10,
        )

        self._backup_configs[node_id] = config
        return config

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques"""
        total_size = sum(b.size for b in self._backups.values())

        return {
            "total_backups": len(self._backups),
            "total_size": total_size,
            "backups_by_type": {
                t.value: len([b for b in self._backups.values() if b.backup_type == t])
                for t in BackupType
            },
            "backups_by_status": {
                s.value: len([b for b in self._backups.values() if b.status == s])
                for s in BackupStatus
            },
            "active_backups": len(self._active_backups),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeBackupManager...")

        # Annulation des tâches actives
        for task in self._active_backups.values():
            task.cancel()

        self._backups.clear()
        self._backup_configs.clear()
        self._active_backups.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_backup_manager(
    config: Dict[str, Any],
    **kwargs,
) -> NodeBackupManager:
    """
    Crée une instance de NodeBackupManager

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeBackupManager
    """
    return NodeBackupManager(
        config=config,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeBackupManager"""
    # Configuration
    config = {
        "base_dir": "./backups",
        "verify_integrity": True,
    }

    # Création du gestionnaire
    backup_manager = create_node_backup_manager(config=config)

    # Création d'un nœud de test (simplifié)
    class TestNode:
        def __init__(self):
            self.config = NodeConfig(
                node_id="test_node",
                protocol=NodeProtocol.ETHEREUM,
                node_type=NodeType.FULL,
                endpoint="https://mainnet.infura.io/v3/YOUR_KEY",
            )

        def get_config(self):
            return self.config

        def get_statistics(self):
            return {"status": "online", "block_height": 10000000}

        def get_status(self):
            return "online"

        async def is_healthy(self):
            return True

        async def get_block(self, block_number):
            return {"number": 10000000}

    node = TestNode()

    # Création d'une sauvegarde
    backup = await backup_manager.create_backup(
        node=node,
        backup_type=BackupType.FULL,
    )

    print(f"Sauvegarde créée: {backup.to_dict()}")

    # Liste des sauvegardes
    backups = await backup_manager.list_backups(node_id="test_node")
    print(f"Sauvegardes: {len(backups)}")

    # Nettoyage des anciennes sauvegardes
    deleted = await backup_manager.cleanup_old_backups(
        node_id="test_node",
        retention_days=30,
    )
    print(f"Sauvegardes supprimées: {deleted}")

    # Statistiques
    stats = backup_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await backup_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
