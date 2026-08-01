# trading/bots/hedge_bot/hedge_bot_data_lifecycle.py
# Advanced Data Lifecycle Management & Retention Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Lifecycle Module - Module avancé de gestion du cycle de vie des données pour le Hedge Bot.
Gère la rétention des données, l'archivage, la purge, la migration, le tiering,
et la conformité réglementaire pour l'ensemble des données du système de hedging.
"""

import asyncio
import json
import time
import shutil
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
import pickle
import zlib
import gzip
from pathlib import Path
import aiofiles
import aiofiles.os

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_lifecycle")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class DataTier(Enum):
    """Tiers de données."""
    HOT = "hot"                        # Données chaudes (accès fréquent)
    WARM = "warm"                      # Données tièdes (accès modéré)
    COLD = "cold"                      # Données froides (accès rare)
    ARCHIVE = "archive"                # Données archivées (accès très rare)
    FROZEN = "frozen"                  # Données gelées (conservation légale)


class LifecyclePolicy(Enum):
    """Politiques de cycle de vie."""
    DELETE = "delete"                  # Suppression
    ARCHIVE = "archive"                # Archivage
    COMPRESS = "compress"              # Compression
    MOVE = "move"                      # Déplacement
    EXPIRY = "expiry"                  # Expiration
    AGGREGATE = "aggregate"            # Agrégation
    ANONYMIZE = "anonymize"            # Anonymisation


class DataRetentionPeriod(Enum):
    """Périodes de rétention."""
    HOURS_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    DAYS_90 = "90d"
    DAYS_180 = "180d"
    DAYS_365 = "365d"
    YEARS_3 = "3y"
    YEARS_5 = "5y"
    YEARS_7 = "7y"
    INDEFINITE = "indefinite"


# ============== DATA MODELS ==============

@dataclass
class LifecycleRule:
    """Règle de cycle de vie."""
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    data_type: DataType = DataType.MARKET
    tier: DataTier = DataTier.HOT
    retention_period: DataRetentionPeriod = DataRetentionPeriod.DAYS_90
    policy: LifecyclePolicy = LifecyclePolicy.DELETE
    conditions: Dict[str, Any] = field(default_factory=dict)
    target_tier: Optional[DataTier] = None
    compression: bool = False
    encryption: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    priority: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DataLifecycleEvent:
    """Événement de cycle de vie."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_type: DataType = DataType.MARKET
    record_id: str = ""
    from_tier: DataTier = DataTier.HOT
    to_tier: DataTier = DataTier.HOT
    policy: LifecyclePolicy = LifecyclePolicy.MOVE
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    size_bytes: int = 0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataLifecycleStats:
    """Statistiques du cycle de vie."""
    stats_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_type: DataType = DataType.MARKET
    tier_counts: Dict[DataTier, int] = field(default_factory=dict)
    tier_sizes: Dict[DataTier, int] = field(default_factory=dict)
    total_records: int = 0
    total_size_bytes: int = 0
    archived_count: int = 0
    deleted_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class LifecycleEngineInterface(ABC):
    """Interface abstraite pour le moteur de cycle de vie."""
    
    @abstractmethod
    async def create_rule(self, rule: LifecycleRule) -> str:
        """Crée une règle de cycle de vie."""
        pass
    
    @abstractmethod
    async def apply_policy(self, data_type: DataType) -> int:
        """Applique les politiques de cycle de vie."""
        pass
    
    @abstractmethod
    async def get_stats(self, data_type: DataType) -> DataLifecycleStats:
        """Récupère les statistiques du cycle de vie."""
        pass


# ============== IMPLÉMENTATION ==============

class LifecycleEngine(LifecycleEngineInterface):
    """
    Moteur de cycle de vie avancé pour le Hedge Bot.
    Gère la rétention, l'archivage, la purge et la conformité des données.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des règles
        self._rules: Dict[str, LifecycleRule] = {}
        self._rules_lock = threading.RLock()
        
        # Gestion des événements
        self._events: deque = deque(maxlen=10000)
        self._events_lock = threading.RLock()
        
        # Gestion des statistiques
        self._stats: Dict[DataType, DataLifecycleStats] = {}
        self._stats_lock = threading.RLock()
        
        # Tiers de données
        self._data_tiers: Dict[str, Path] = {}
        self._tiers_lock = threading.RLock()
        
        # Statistiques
        self._global_stats: Dict[str, Any] = {
            "rules_created": 0,
            "records_moved": 0,
            "records_archived": 0,
            "records_deleted": 0,
            "records_compressed": 0,
            "total_data_saved_mb": 0.0,
            "avg_processing_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Dossiers des tiers
        self._base_path = Path(self.config.get("base_path", "./lifecycle_data"))
        self._setup_tiers()
        
        logger.info("LifecycleEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "base_path": "./lifecycle_data",
            "hot_path": "./lifecycle_data/hot",
            "warm_path": "./lifecycle_data/warm",
            "cold_path": "./lifecycle_data/cold",
            "archive_path": "./lifecycle_data/archive",
            "frozen_path": "./lifecycle_data/frozen",
            "default_policy": LifecyclePolicy.DELETE,
            "default_retention": DataRetentionPeriod.DAYS_90,
            "batch_size": 1000,
            "processing_interval": 3600,
            "enable_compression": True,
            "enable_encryption": True,
            "compression_threshold": 1024,
            "max_events": 10000,
            "retention_override": {}
        }
    
    async def start(self) -> None:
        """Démarre le moteur de cycle de vie."""
        logger.info("LifecycleEngine starting...")
        self._is_running = True
        
        # Chargement des règles existantes
        await self._load_rules()
        
        # Création des règles par défaut
        await self._create_default_rules()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._lifecycle_processor())
        asyncio.create_task(self._stats_collector())
        asyncio.create_task(self._event_cleaner())
        
        logger.info("LifecycleEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de cycle de vie."""
        logger.info("LifecycleEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("LifecycleEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_rule(self, rule: LifecycleRule) -> str:
        """Crée une règle de cycle de vie."""
        with self._rules_lock:
            self._rules[rule.rule_id] = rule
            self._global_stats["rules_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"lifecycle:rule:{rule.rule_id}",
                rule.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Lifecycle rule created: {rule.name} (id={rule.rule_id})")
        return rule.rule_id
    
    async def apply_policy(self, data_type: DataType) -> int:
        """Applique les politiques de cycle de vie."""
        start_time = time.time()
        processed = 0
        
        try:
            # Récupération des règles pour ce type de données
            rules = await self._get_rules_for_type(data_type)
            
            if not rules:
                return 0
            
            # Récupération des données
            if not self.data_manager:
                return 0
            
            # Application des règles
            for rule in rules:
                if not rule.active:
                    continue
                
                records = await self._get_data_for_type(data_type, rule)
                
                for record in records:
                    await self._apply_rule(record, rule)
                    processed += 1
            
            # Mise à jour des statistiques
            await self._update_stats(data_type)
            
            duration_ms = (time.time() - start_time) * 1000
            self._global_stats["avg_processing_time_ms"] = (
                self._global_stats["avg_processing_time_ms"] * 0.9 + duration_ms * 0.1
            )
            
            logger.info(f"Applied lifecycle policies to {processed} records for {data_type.value}")
            return processed
            
        except Exception as e:
            logger.error(f"Apply policy error: {e}")
            return processed
    
    async def get_stats(self, data_type: DataType) -> DataLifecycleStats:
        """Récupère les statistiques du cycle de vie."""
        with self._stats_lock:
            if data_type in self._stats:
                return self._stats[data_type]
        
        # Création de statistiques vides
        stats = DataLifecycleStats(data_type=data_type)
        with self._stats_lock:
            self._stats[data_type] = stats
        
        return stats
    
    # ========== MÉTHODES PRIVÉES - TIERS ==========
    
    def _setup_tiers(self) -> None:
        """Configure les tiers de données."""
        tiers = {
            DataTier.HOT: self.config["hot_path"],
            DataTier.WARM: self.config["warm_path"],
            DataTier.COLD: self.config["cold_path"],
            DataTier.ARCHIVE: self.config["archive_path"],
            DataTier.FROZEN: self.config["frozen_path"]
        }
        
        for tier, path in tiers.items():
            tier_path = Path(path)
            tier_path.mkdir(parents=True, exist_ok=True)
            
            with self._tiers_lock:
                self._data_tiers[tier.value] = tier_path
        
        logger.info("Data tiers configured")
    
    async def _move_to_tier(self, record_id: str, from_tier: DataTier, to_tier: DataTier) -> bool:
        """Déplace un enregistrement vers un autre tier."""
        try:
            from_path = self._data_tiers.get(from_tier.value)
            to_path = self._data_tiers.get(to_tier.value)
            
            if not from_path or not to_path:
                return False
            
            source = from_path / f"{record_id}.data"
            destination = to_path / f"{record_id}.data"
            
            if not source.exists():
                return False
            
            # Déplacement du fichier
            shutil.move(str(source), str(destination))
            
            # Enregistrement de l'événement
            event = DataLifecycleEvent(
                data_type=DataType.MARKET,
                record_id=record_id,
                from_tier=from_tier,
                to_tier=to_tier,
                policy=LifecyclePolicy.MOVE,
                size_bytes=destination.stat().st_size if destination.exists() else 0
            )
            
            with self._events_lock:
                self._events.append(event)
            
            self._global_stats["records_moved"] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Move to tier error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - RÈGLES ==========
    
    async def _get_rules_for_type(self, data_type: DataType) -> List[LifecycleRule]:
        """Récupère les règles pour un type de données."""
        with self._rules_lock:
            return [r for r in self._rules.values() if r.data_type == data_type and r.active]
    
    async def _apply_rule(self, record: Dict[str, Any], rule: LifecycleRule) -> None:
        """Applique une règle à un enregistrement."""
        record_id = record.get("id", "")
        age_days = record.get("age_days", 0)
        
        # Vérification des conditions
        if not self._check_conditions(record, rule.conditions):
            return
        
        # Détermination de l'action
        retention_days = self._parse_retention_period(rule.retention_period)
        
        if age_days < retention_days:
            return
        
        if rule.policy == LifecyclePolicy.DELETE:
            await self._delete_record(record_id, rule.data_type)
            self._global_stats["records_deleted"] += 1
            
        elif rule.policy == LifecyclePolicy.ARCHIVE:
            # Déplacement vers Archive
            if await self._move_to_tier(record_id, rule.tier, DataTier.ARCHIVE):
                self._global_stats["records_archived"] += 1
                
        elif rule.policy == LifecyclePolicy.COMPRESS:
            if await self._compress_record(record_id, rule):
                self._global_stats["records_compressed"] += 1
                
        elif rule.policy == LifecyclePolicy.MOVE:
            # Déplacement vers le tier cible
            if rule.target_tier:
                await self._move_to_tier(record_id, rule.tier, rule.target_tier)
    
    def _check_conditions(self, record: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """Vérifie les conditions d'une règle."""
        for key, value in conditions.items():
            if key in record:
                if isinstance(value, dict):
                    op = value.get("operator", "eq")
                    val = value.get("value")
                    
                    if op == "eq" and record[key] != val:
                        return False
                    elif op == "ne" and record[key] == val:
                        return False
                    elif op == "gt" and record[key] <= val:
                        return False
                    elif op == "gte" and record[key] < val:
                        return False
                    elif op == "lt" and record[key] >= val:
                        return False
                    elif op == "lte" and record[key] > val:
                        return False
                else:
                    if record[key] != value:
                        return False
        
        return True
    
    def _parse_retention_period(self, period: DataRetentionPeriod) -> int:
        """Parse une période de rétention en jours."""
        mapping = {
            DataRetentionPeriod.HOURS_24: 1,
            DataRetentionPeriod.DAYS_7: 7,
            DataRetentionPeriod.DAYS_30: 30,
            DataRetentionPeriod.DAYS_90: 90,
            DataRetentionPeriod.DAYS_180: 180,
            DataRetentionPeriod.DAYS_365: 365,
            DataRetentionPeriod.YEARS_3: 1095,
            DataRetentionPeriod.YEARS_5: 1825,
            DataRetentionPeriod.YEARS_7: 2555,
            DataRetentionPeriod.INDEFINITE: 999999
        }
        return mapping.get(period, 90)
    
    # ========== MÉTHODES PRIVÉES - OPÉRATIONS ==========
    
    async def _delete_record(self, record_id: str, data_type: DataType) -> bool:
        """Supprime un enregistrement."""
        if self.data_manager:
            try:
                await self.data_manager.delete(record_id, data_type)
                return True
            except Exception as e:
                logger.error(f"Delete record error: {e}")
                return False
        return False
    
    async def _compress_record(self, record_id: str, rule: LifecycleRule) -> bool:
        """Compresse un enregistrement."""
        try:
            # Récupération du chemin
            tier_path = self._data_tiers.get(rule.tier.value)
            if not tier_path:
                return False
            
            file_path = tier_path / f"{record_id}.data"
            if not file_path.exists():
                return False
            
            # Compression
            compressed_path = tier_path / f"{record_id}.data.gz"
            
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Suppression du fichier original
            file_path.unlink()
            
            # Enregistrement de l'événement
            event = DataLifecycleEvent(
                data_type=rule.data_type,
                record_id=record_id,
                from_tier=rule.tier,
                to_tier=rule.tier,
                policy=LifecyclePolicy.COMPRESS,
                size_bytes=compressed_path.stat().st_size
            )
            
            with self._events_lock:
                self._events.append(event)
            
            return True
            
        except Exception as e:
            logger.error(f"Compress record error: {e}")
            return False
    
    async def _get_data_for_type(self, data_type: DataType, rule: LifecycleRule) -> List[Dict[str, Any]]:
        """Récupère les données pour un type et une règle."""
        if not self.data_manager:
            return []
        
        try:
            # Dans un système réel, on interrogerait la base de données
            # avec des filtres appropriés
            records = await self.data_manager.retrieve_all(data_type)
            
            # Filtrage par âge
            now = datetime.now(timezone.utc)
            filtered = []
            
            for record in records:
                if not record.value:
                    continue
                
                # Calcul de l'âge en jours
                created_at = record.value.get("created_at")
                if created_at:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at)
                    age = (now - created_at).total_seconds() / (24 * 3600)
                    record.value["age_days"] = age
                
                filtered.append(record.value)
            
            return filtered
            
        except Exception as e:
            logger.error(f"Get data error: {e}")
            return []
    
    # ========== MÉTHODES PRIVÉES - STATISTIQUES ==========
    
    async def _update_stats(self, data_type: DataType) -> None:
        """Met à jour les statistiques."""
        try:
            tier_counts = {}
            tier_sizes = {}
            total_records = 0
            total_size = 0
            
            for tier, path in self._data_tiers.items():
                count = len(list(path.glob("*.data")))
                size = sum(f.stat().st_size for f in path.glob("*.data"))
                
                tier_counts[DataTier(tier)] = count
                tier_sizes[DataTier(tier)] = size
                total_records += count
                total_size += size
            
            stats = DataLifecycleStats(
                data_type=data_type,
                tier_counts=tier_counts,
                tier_sizes=tier_sizes,
                total_records=total_records,
                total_size_bytes=total_size,
                archived_count=tier_counts.get(DataTier.ARCHIVE, 0),
                deleted_count=self._global_stats["records_deleted"]
            )
            
            with self._stats_lock:
                self._stats[data_type] = stats
            
        except Exception as e:
            logger.error(f"Update stats error: {e}")
    
    # ========== MÉTHODES PRIVÉES - CHARGEMENT ==========
    
    async def _load_rules(self) -> None:
        """Charge les règles existantes."""
        try:
            if self.data_manager:
                rules_data = await self.data_manager.retrieve(
                    "lifecycle:rules",
                    DataType.CONFIG
                )
                
                if rules_data:
                    for rule_dict in rules_data:
                        rule = self._deserialize_rule(rule_dict)
                        if rule:
                            with self._rules_lock:
                                self._rules[rule.rule_id] = rule
            
            logger.info(f"Loaded {len(self._rules)} lifecycle rules")
            
        except Exception as e:
            logger.error(f"Load rules error: {e}")
    
    async def _create_default_rules(self) -> None:
        """Crée les règles par défaut."""
        default_rules = [
            LifecycleRule(
                name="Market Data Retention",
                data_type=DataType.MARKET,
                retention_period=DataRetentionPeriod.DAYS_90,
                policy=LifecyclePolicy.DELETE,
                priority=1
            ),
            LifecycleRule(
                name="Trade Data Retention",
                data_type=DataType.TRADE,
                retention_period=DataRetentionPeriod.YEARS_5,
                policy=LifecyclePolicy.ARCHIVE,
                priority=2
            ),
            LifecycleRule(
                name="Risk Data Retention",
                data_type=DataType.RISK,
                retention_period=DataRetentionPeriod.DAYS_365,
                policy=LifecyclePolicy.COMPRESS,
                priority=3
            ),
            LifecycleRule(
                name="Log Data Retention",
                data_type=DataType.LOG,
                retention_period=DataRetentionPeriod.DAYS_30,
                policy=LifecyclePolicy.DELETE,
                priority=4
            ),
            LifecycleRule(
                name="Performance Data Retention",
                data_type=DataType.PERFORMANCE,
                retention_period=DataRetentionPeriod.DAYS_365,
                policy=LifecyclePolicy.COMPRESS,
                priority=5
            )
        ]
        
        for rule in default_rules:
            # Vérification si la règle existe déjà
            exists = False
            with self._rules_lock:
                for existing in self._rules.values():
                    if existing.name == rule.name:
                        exists = True
                        break
            
            if not exists:
                await self.create_rule(rule)
    
    def _deserialize_rule(self, data: Dict) -> Optional[LifecycleRule]:
        """Désérialise une règle."""
        try:
            return LifecycleRule(
                rule_id=data.get("rule_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                data_type=DataType(data.get("data_type", "market")),
                tier=DataTier(data.get("tier", "hot")),
                retention_period=DataRetentionPeriod(data.get("retention_period", "90d")),
                policy=LifecyclePolicy(data.get("policy", "delete")),
                conditions=data.get("conditions", {}),
                target_tier=DataTier(data.get("target_tier")) if data.get("target_tier") else None,
                compression=data.get("compression", False),
                encryption=data.get("encryption", False),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                priority=data.get("priority", 1),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing rule: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _lifecycle_processor(self) -> None:
        """Traite les politiques de cycle de vie."""
        while self._is_running:
            await asyncio.sleep(self.config["processing_interval"])
            
            try:
                # Application des politiques pour chaque type de données
                for data_type in DataType:
                    await self.apply_policy(data_type)
                
                # Mise à jour des statistiques globales
                self._global_stats["total_data_saved_mb"] = (
                    self._global_stats["records_compressed"] * 0.5 + 
                    self._global_stats["records_archived"] * 1.0
                )
                
            except Exception as e:
                logger.error(f"Lifecycle processor error: {e}")
    
    async def _stats_collector(self) -> None:
        """Collecte les statistiques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques pour chaque type
                for data_type in DataType:
                    await self._update_stats(data_type)
                
                # Stockage des statistiques
                if self.data_manager:
                    await self.data_manager.store(
                        "lifecycle:global_stats",
                        self._global_stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Stats collector error: {e}")
    
    async def _event_cleaner(self) -> None:
        """Nettoie les événements anciens."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                
                with self._events_lock:
                    # Suppression des événements anciens
                    while self._events and self._events[0].timestamp < cutoff:
                        self._events.popleft()
                
            except Exception as e:
                logger.error(f"Event cleaner error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_rule(self, rule_id: str) -> Optional[LifecycleRule]:
        """Récupère une règle."""
        with self._rules_lock:
            return self._rules.get(rule_id)
    
    async def get_rules(self, active_only: bool = True) -> List[LifecycleRule]:
        """Récupère les règles."""
        with self._rules_lock:
            rules = list(self._rules.values())
            if active_only:
                rules = [r for r in rules if r.active]
            return sorted(rules, key=lambda r: r.priority)
    
    async def get_events(self, limit: int = 100) -> List[DataLifecycleEvent]:
        """Récupère les événements récents."""
        with self._events_lock:
            return list(self._events)[-limit:]
    
    async def get_tier_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques des tiers."""
        stats = {}
        for tier, path in self._data_tiers.items():
            count = len(list(path.glob("*.data")))
            size = sum(f.stat().st_size for f in path.glob("*.data"))
            stats[tier] = {
                "count": count,
                "size_bytes": size,
                "size_mb": size / (1024 * 1024)
            }
        return stats
    
    async def purge_data(self, data_type: DataType, days: int) -> int:
        """Purge les données plus anciennes que x jours."""
        try:
            # Création d'une règle temporaire
            rule = LifecycleRule(
                name=f"Purge_{data_type.value}_{days}d",
                data_type=data_type,
                retention_period=DataRetentionPeriod(f"{days}d"),
                policy=LifecyclePolicy.DELETE
            )
            
            # Application de la règle
            return await self.apply_policy(data_type)
            
        except Exception as e:
            logger.error(f"Purge data error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques globales."""
        with self._rules_lock:
            self._global_stats["total_rules"] = len(self._rules)
        
        return self._global_stats.copy()


# ============== FACTORY ==============

class LifecycleFactory:
    """Factory pour créer des composants de cycle de vie."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LifecycleEngine:
        """Crée un moteur de cycle de vie."""
        engine = LifecycleEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "DataTier",
    "LifecyclePolicy",
    "DataRetentionPeriod",
    "LifecycleRule",
    "DataLifecycleEvent",
    "DataLifecycleStats",
    "LifecycleEngineInterface",
    "LifecycleEngine",
    "LifecycleFactory"
]
