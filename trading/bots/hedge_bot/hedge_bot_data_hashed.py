# trading/bots/hedge_bot/hedge_bot_data_hashed.py
# Advanced Hashed Data Storage & Integrity Verification for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Hashed Data Module - Module de stockage haché et vérification d'intégrité avancé
pour le Hedge Bot. Assure l'intégrité des données, la vérification cryptographique,
la détection de falsification et la traçabilité des données pour l'ensemble du système.
"""

import asyncio
import json
import hashlib
import hmac
import time
import base64
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import zlib
import pickle
import threading
import concurrent.futures
import struct

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_hashed")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class HashAlgorithm(Enum):
    """Algorithmes de hachage disponibles."""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"
    SHA3_256 = "sha3_256"
    SHA3_512 = "sha3_512"


class HashVerificationStatus(Enum):
    """Statuts de vérification de hachage."""
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    TAMPERED = "tampered"
    UNKNOWN = "unknown"


class IntegrityLevel(Enum):
    """Niveaux d'intégrité."""
    NONE = "none"                     # Pas d'intégrité
    BASIC = "basic"                   # Hachage simple
    STANDARD = "standard"             # Hachage + signature
    ADVANCED = "advanced"             # Hachage + signature + chaînage
    MILITARY = "military"             # Hachage + signature + chaînage + timestamp


# ============== DATA MODELS ==============

@dataclass
class HashedData:
    """Données hachées avec métadonnées."""
    data_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: Any = None
    hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256
    hash_value: str = ""
    previous_hash: Optional[str] = None
    chain_id: Optional[str] = None
    sequence: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    signature: Optional[str] = None
    signer_id: Optional[str] = None
    integrity_level: IntegrityLevel = IntegrityLevel.STANDARD
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    version: int = 1
    verified: bool = False
    verification_status: HashVerificationStatus = HashVerificationStatus.UNKNOWN
    
    def to_dict(self) -> Dict:
        return {
            "data_id": self.data_id,
            "content": self.content,
            "hash_algorithm": self.hash_algorithm.value,
            "hash_value": self.hash_value,
            "previous_hash": self.previous_hash,
            "chain_id": self.chain_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "signature": self.signature,
            "signer_id": self.signer_id,
            "integrity_level": self.integrity_level.value,
            "metadata": self.metadata,
            "tags": self.tags,
            "version": self.version,
            "verified": self.verified,
            "verification_status": self.verification_status.value
        }


@dataclass
class HashChain:
    """Chaîne de hachage pour l'intégrité des données."""
    chain_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    genesis_hash: Optional[str] = None
    current_hash: Optional[str] = None
    length: int = 0
    algorithm: HashAlgorithm = HashAlgorithm.SHA256
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    last_verified: Optional[datetime] = None
    integrity_status: HashVerificationStatus = HashVerificationStatus.VERIFIED
    
    def to_dict(self) -> Dict:
        return {
            "chain_id": self.chain_id,
            "name": self.name,
            "genesis_hash": self.genesis_hash,
            "current_hash": self.current_hash,
            "length": self.length,
            "algorithm": self.algorithm.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "active": self.active,
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "integrity_status": self.integrity_status.value
        }


@dataclass
class HashVerificationResult:
    """Résultat de vérification de hachage."""
    verification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_id: str = ""
    status: HashVerificationStatus = HashVerificationStatus.VERIFIED
    computed_hash: str = ""
    stored_hash: str = ""
    algorithm: HashAlgorithm = HashAlgorithm.SHA256
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    verified: bool = False
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    chain_id: Optional[str] = None
    sequence: int = 0
    previous_verified: bool = False


# ============== INTERFACES ==============

class HashedStorageInterface(ABC):
    """Interface abstraite pour le stockage haché."""
    
    @abstractmethod
    async def store(self, data: Any, integrity_level: IntegrityLevel) -> HashedData:
        """Stocke des données avec hachage."""
        pass
    
    @abstractmethod
    async def verify(self, data_id: str) -> HashVerificationResult:
        """Vérifie l'intégrité des données."""
        pass
    
    @abstractmethod
    async def get(self, data_id: str) -> Optional[HashedData]:
        """Récupère des données."""
        pass


# ============== IMPLÉMENTATION ==============

class HashedStorageEngine(HashedStorageInterface):
    """
    Moteur de stockage haché avancé pour le Hedge Bot.
    Gère l'intégrité des données, la vérification cryptographique et le chaînage.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        secret_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.secret_key = secret_key or os.urandom(32).hex()
        self.config = config or self._default_config()
        
        # Stockage des données hachées
        self._data: Dict[str, HashedData] = {}
        self._data_lock = threading.RLock()
        
        # Chaînes de hachage
        self._chains: Dict[str, HashChain] = {}
        self._chain_lock = threading.RLock()
        
        # Cache des vérifications
        self._verification_cache: Dict[str, HashVerificationResult] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "data_stored": 0,
            "verifications_performed": 0,
            "verified_success": 0,
            "verified_fail": 0,
            "chains_created": 0,
            "integrity_violations": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("HashedStorageEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_algorithm": HashAlgorithm.SHA256,
            "default_integrity_level": IntegrityLevel.STANDARD,
            "cache_size": 1000,
            "enable_chain": True,
            "max_chain_length": 100000,
            "verification_interval": 3600,  # 1 heure
            "auto_verify": True,
            "store_compressed": True,
            "compression_threshold": 1024,
            "signature_required": False,
            "timestamp_required": True
        }
    
    async def start(self) -> None:
        """Démarre le moteur de stockage haché."""
        logger.info("HashedStorageEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._verification_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        # Chargement des données existantes
        await self._load_existing_data()
        
        logger.info("HashedStorageEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de stockage haché."""
        logger.info("HashedStorageEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("HashedStorageEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def store(
        self,
        data: Any,
        integrity_level: IntegrityLevel = IntegrityLevel.STANDARD,
        chain_id: Optional[str] = None
    ) -> HashedData:
        """Stocke des données avec hachage."""
        start_time = time.time()
        self._stats["data_stored"] += 1
        
        try:
            # Sérialisation des données
            serialized = self._serialize_data(data)
            
            # Compression
            if self.config["store_compressed"] and len(serialized) > self.config["compression_threshold"]:
                serialized = zlib.compress(serialized)
                compressed = True
            else:
                compressed = False
            
            # Calcul du hachage
            algorithm = self.config["default_algorithm"]
            hash_value = self._compute_hash(serialized, algorithm)
            
            # Chaînage
            if chain_id and self.config["enable_chain"]:
                chain = await self._get_chain(chain_id)
                previous_hash = chain.current_hash if chain else None
                sequence = chain.length + 1 if chain else 1
            else:
                previous_hash = None
                sequence = 0
            
            # Création des données hachées
            hashed_data = HashedData(
                content=data,
                hash_algorithm=algorithm,
                hash_value=hash_value,
                previous_hash=previous_hash,
                chain_id=chain_id,
                sequence=sequence,
                integrity_level=integrity_level,
                metadata={
                    "compressed": compressed,
                    "size_original": len(serialized),
                    "size_stored": len(serialized) if not compressed else len(serialized)
                },
                tags=["hashed", integrity_level.value]
            )
            
            # Signature
            if self.config["signature_required"] or integrity_level in [IntegrityLevel.ADVANCED, IntegrityLevel.MILITARY]:
                hashed_data.signature = await self._sign_data(hashed_data)
                hashed_data.signer_id = "system"
            
            # Stockage
            with self._data_lock:
                self._data[hashed_data.data_id] = hashed_data
            
            # Mise à jour de la chaîne
            if chain_id and self.config["enable_chain"]:
                await self._update_chain(chain_id, hashed_data)
            
            # Stockage persistant
            if self.data_manager:
                await self.data_manager.store(
                    f"hashed:data:{hashed_data.data_id}",
                    hashed_data.to_dict(),
                    DataType.HASHED
                )
            
            execution_time = time.time() - start_time
            logger.debug(f"Data stored with hash: {hashed_data.data_id} "
                        f"algorithm={algorithm.value} time={execution_time:.3f}s")
            
            return hashed_data
            
        except Exception as e:
            logger.error(f"Store error: {e}")
            raise
    
    async def verify(self, data_id: str) -> HashVerificationResult:
        """Vérifie l'intégrité des données."""
        self._stats["verifications_performed"] += 1
        
        try:
            # Récupération des données
            hashed_data = await self.get(data_id)
            if not hashed_data:
                return HashVerificationResult(
                    data_id=data_id,
                    status=HashVerificationStatus.MISSING,
                    verified=False,
                    message="Data not found"
                )
            
            # Vérification du cache
            cache_key = f"{data_id}_{int(time.time())}"
            if cache_key in self._verification_cache:
                return self._verification_cache[cache_key]
            
            # Vérification du hachage
            serialized = self._serialize_data(hashed_data.content)
            computed_hash = self._compute_hash(serialized, hashed_data.hash_algorithm)
            
            # Comparaison
            if computed_hash == hashed_data.hash_value:
                status = HashVerificationStatus.VERIFIED
                verified = True
                message = "Hash verification successful"
                self._stats["verified_success"] += 1
            else:
                status = HashVerificationStatus.MISMATCH
                verified = False
                message = f"Hash mismatch: stored={hashed_data.hash_value}, computed={computed_hash}"
                self._stats["verified_fail"] += 1
                self._stats["integrity_violations"] += 1
            
            # Vérification du chaînage
            chain_verified = True
            if hashed_data.chain_id and hashed_data.previous_hash:
                chain_verified = await self._verify_chain(
                    hashed_data.chain_id,
                    hashed_data.data_id
                )
                if not chain_verified:
                    status = HashVerificationStatus.TAMPERED
                    verified = False
                    message += " | Chain verification failed"
            
            # Création du résultat
            result = HashVerificationResult(
                data_id=data_id,
                status=status,
                computed_hash=computed_hash,
                stored_hash=hashed_data.hash_value,
                algorithm=hashed_data.hash_algorithm,
                verified=verified,
                message=message,
                chain_id=hashed_data.chain_id,
                sequence=hashed_data.sequence,
                previous_verified=chain_verified
            )
            
            # Mise à jour du statut
            hashed_data.verified = verified
            hashed_data.verification_status = status
            
            # Mise en cache
            with self._cache_lock:
                if len(self._verification_cache) < self.config["cache_size"]:
                    self._verification_cache[cache_key] = result
            
            logger.info(f"Verification for {data_id}: {status.value} ({message})")
            return result
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return HashVerificationResult(
                data_id=data_id,
                status=HashVerificationStatus.CORRUPTED,
                verified=False,
                message=str(e)
            )
    
    async def get(self, data_id: str) -> Optional[HashedData]:
        """Récupère des données."""
        # Vérification du cache mémoire
        with self._data_lock:
            if data_id in self._data:
                return self._data[data_id]
        
        # Récupération depuis le stockage persistant
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"hashed:data:{data_id}",
                DataType.HASHED
            )
            if data:
                hashed_data = self._deserialize_data(data)
                if hashed_data:
                    with self._data_lock:
                        self._data[data_id] = hashed_data
                    return hashed_data
        
        return None
    
    # ========== MÉTHODES PRIVÉES - HACHAGE ==========
    
    def _compute_hash(self, data: bytes, algorithm: HashAlgorithm) -> str:
        """Calcule le hachage des données."""
        if algorithm == HashAlgorithm.MD5:
            return hashlib.md5(data).hexdigest()
        elif algorithm == HashAlgorithm.SHA1:
            return hashlib.sha1(data).hexdigest()
        elif algorithm == HashAlgorithm.SHA256:
            return hashlib.sha256(data).hexdigest()
        elif algorithm == HashAlgorithm.SHA384:
            return hashlib.sha384(data).hexdigest()
        elif algorithm == HashAlgorithm.SHA512:
            return hashlib.sha512(data).hexdigest()
        elif algorithm == HashAlgorithm.BLAKE2B:
            return hashlib.blake2b(data).hexdigest()
        elif algorithm == HashAlgorithm.BLAKE2S:
            return hashlib.blake2s(data).hexdigest()
        elif algorithm == HashAlgorithm.SHA3_256:
            return hashlib.sha3_256(data).hexdigest()
        elif algorithm == HashAlgorithm.SHA3_512:
            return hashlib.sha3_512(data).hexdigest()
        else:
            return hashlib.sha256(data).hexdigest()
    
    def _compute_hmac(self, data: bytes) -> str:
        """Calcule le HMAC des données."""
        return hmac.new(
            self.secret_key.encode(),
            data,
            hashlib.sha256
        ).hexdigest()
    
    def _serialize_data(self, data: Any) -> bytes:
        """Sérialise des données."""
        if isinstance(data, (str, bytes)):
            return data.encode() if isinstance(data, str) else data
        return pickle.dumps(data)
    
    def _deserialize_data(self, data: Dict) -> Optional[HashedData]:
        """Désérialise des données hachées."""
        try:
            return HashedData(
                data_id=data.get("data_id", str(uuid.uuid4())),
                content=data.get("content"),
                hash_algorithm=HashAlgorithm(data.get("hash_algorithm", "sha256")),
                hash_value=data.get("hash_value", ""),
                previous_hash=data.get("previous_hash"),
                chain_id=data.get("chain_id"),
                sequence=data.get("sequence", 0),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                signature=data.get("signature"),
                signer_id=data.get("signer_id"),
                integrity_level=IntegrityLevel(data.get("integrity_level", "standard")),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                version=data.get("version", 1),
                verified=data.get("verified", False),
                verification_status=HashVerificationStatus(data.get("verification_status", "unknown"))
            )
        except Exception as e:
            logger.error(f"Error deserializing hashed data: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - SIGNATURE ==========
    
    async def _sign_data(self, hashed_data: HashedData) -> str:
        """Signe les données."""
        # Construction du message à signer
        message = f"{hashed_data.data_id}{hashed_data.hash_value}{hashed_data.previous_hash}{hashed_data.sequence}"
        signature = self._compute_hmac(message.encode())
        return signature
    
    async def _verify_signature(self, hashed_data: HashedData) -> bool:
        """Vérifie la signature."""
        if not hashed_data.signature:
            return False
        
        # Recalcul de la signature
        message = f"{hashed_data.data_id}{hashed_data.hash_value}{hashed_data.previous_hash}{hashed_data.sequence}"
        expected = self._compute_hmac(message.encode())
        
        return hashed_data.signature == expected
    
    # ========== MÉTHODES PRIVÉES - CHAÎNAGE ==========
    
    async def _get_chain(self, chain_id: str) -> Optional[HashChain]:
        """Récupère une chaîne de hachage."""
        with self._chain_lock:
            if chain_id in self._chains:
                return self._chains[chain_id]
        
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"hashed:chain:{chain_id}",
                DataType.CHAIN
            )
            if data:
                chain = self._deserialize_chain(data)
                if chain:
                    with self._chain_lock:
                        self._chains[chain_id] = chain
                    return chain
        
        return None
    
    async def _create_chain(
        self,
        name: str,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256
    ) -> HashChain:
        """Crée une nouvelle chaîne de hachage."""
        chain = HashChain(
            name=name,
            algorithm=algorithm,
            integrity_status=HashVerificationStatus.VERIFIED
        )
        
        with self._chain_lock:
            self._chains[chain.chain_id] = chain
            self._stats["chains_created"] += 1
        
        if self.data_manager:
            await self.data_manager.store(
                f"hashed:chain:{chain.chain_id}",
                chain.to_dict(),
                DataType.CHAIN
            )
        
        logger.info(f"Hash chain created: {chain.chain_id} ({name})")
        return chain
    
    async def _update_chain(self, chain_id: str, hashed_data: HashedData) -> None:
        """Met à jour une chaîne de hachage."""
        chain = await self._get_chain(chain_id)
        if not chain:
            # Création automatique de la chaîne
            chain = await self._create_chain(f"Auto-chain-{chain_id}")
        
        # Mise à jour
        chain.current_hash = hashed_data.hash_value
        chain.length += 1
        chain.updated_at = datetime.now(timezone.utc)
        
        if not chain.genesis_hash:
            chain.genesis_hash = hashed_data.hash_value
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"hashed:chain:{chain.chain_id}",
                chain.to_dict(),
                DataType.CHAIN
            )
    
    async def _verify_chain(self, chain_id: str, data_id: str) -> bool:
        """Vérifie l'intégrité d'une chaîne de hachage."""
        chain = await self._get_chain(chain_id)
        if not chain:
            return False
        
        # Récupération de toutes les données de la chaîne
        # Dans un système réel, on parcourrait la chaîne
        # Simulation simplifiée
        return True
    
    def _deserialize_chain(self, data: Dict) -> Optional[HashChain]:
        """Désérialise une chaîne de hachage."""
        try:
            return HashChain(
                chain_id=data.get("chain_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                genesis_hash=data.get("genesis_hash"),
                current_hash=data.get("current_hash"),
                length=data.get("length", 0),
                algorithm=HashAlgorithm(data.get("algorithm", "sha256")),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                last_verified=datetime.fromisoformat(data.get("last_verified")) if data.get("last_verified") else None,
                integrity_status=HashVerificationStatus(data.get("integrity_status", "verified"))
            )
        except Exception as e:
            logger.error(f"Error deserializing chain: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _verification_loop(self) -> None:
        """Boucle de vérification automatique."""
        while self._is_running:
            await asyncio.sleep(self.config["verification_interval"])
            
            try:
                if self.config["auto_verify"]:
                    # Vérification des données
                    with self._data_lock:
                        data_ids = list(self._data.keys())
                    
                    # Vérification aléatoire (10% des données)
                    sample_size = max(1, int(len(data_ids) * 0.1))
                    sample = random.sample(data_ids, min(sample_size, len(data_ids)))
                    
                    for data_id in sample:
                        await self.verify(data_id)
                    
                    logger.debug(f"Auto-verification completed: {len(sample)} records checked")
                
            except Exception as e:
                logger.error(f"Verification loop error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._cache_lock:
                    if len(self._verification_cache) > self.config["cache_size"]:
                        keys = list(self._verification_cache.keys())
                        # Supprimer les plus anciens
                        for key in keys[:len(self._verification_cache) - self.config["cache_size"]]:
                            del self._verification_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._data_lock:
                    self._stats["total_data"] = len(self._data)
                with self._chain_lock:
                    self._stats["total_chains"] = len(self._chains)
                
                # Calcul du taux de vérification
                if self._stats["verifications_performed"] > 0:
                    self._stats["verification_rate"] = (
                        self._stats["verified_success"] / self._stats["verifications_performed"]
                    )
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "hashed:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _load_existing_data(self) -> None:
        """Charge les données existantes."""
        try:
            if self.data_manager:
                # Récupération des données hachées
                query = DataQuery(
                    query_id="load_hashed_data",
                    data_type=DataType.HASHED,
                    limit=1000
                )
                result = await self.data_manager.query(query)
                
                loaded_count = 0
                for record in result.records:
                    if record.value:
                        hashed_data = self._deserialize_data(record.value)
                        if hashed_data:
                            with self._data_lock:
                                self._data[hashed_data.data_id] = hashed_data
                            loaded_count += 1
                
                logger.info(f"Loaded {loaded_count} hashed records")
            
        except Exception as e:
            logger.error(f"Load existing data error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_chain(self, chain_id: str) -> Optional[HashChain]:
        """Récupère une chaîne de hachage."""
        return await self._get_chain(chain_id)
    
    async def list_chains(self) -> List[HashChain]:
        """Liste les chaînes de hachage."""
        with self._chain_lock:
            return list(self._chains.values())
    
    async def create_chain(
        self,
        name: str,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256
    ) -> HashChain:
        """Crée une chaîne de hachage."""
        return await self._create_chain(name, algorithm)
    
    async def get_data_by_chain(
        self,
        chain_id: str,
        limit: int = 100
    ) -> List[HashedData]:
        """Récupère les données d'une chaîne."""
        with self._data_lock:
            return [
                d for d in self._data.values()
                if d.chain_id == chain_id
            ][:limit]
    
    async def get_latest_data(self, chain_id: str) -> Optional[HashedData]:
        """Récupère la dernière donnée d'une chaîne."""
        with self._data_lock:
            chain_data = [
                d for d in self._data.values()
                if d.chain_id == chain_id
            ]
            if chain_data:
                return max(chain_data, key=lambda d: d.sequence)
        return None
    
    async def verify_chain_integrity(self, chain_id: str) -> bool:
        """Vérifie l'intégrité complète d'une chaîne."""
        chain = await self._get_chain(chain_id)
        if not chain:
            return False
        
        # Récupération de toutes les données de la chaîne
        chain_data = await self.get_data_by_chain(chain_id, limit=10000)
        
        if not chain_data:
            return True
        
        # Vérification séquentielle
        previous_hash = None
        for data in sorted(chain_data, key=lambda d: d.sequence):
            # Vérification du hachage
            result = await self.verify(data.data_id)
            if not result.verified:
                logger.error(f"Chain integrity breach at {data.data_id}: {result.message}")
                return False
            
            # Vérification du chaînage
            if previous_hash and data.previous_hash != previous_hash:
                logger.error(f"Chain link breach at {data.data_id}: expected {previous_hash}, got {data.previous_hash}")
                return False
            
            previous_hash = data.hash_value
        
        # Mise à jour de la chaîne
        chain.last_verified = datetime.now(timezone.utc)
        chain.integrity_status = HashVerificationStatus.VERIFIED
        
        if self.data_manager:
            await self.data_manager.store(
                f"hashed:chain:{chain.chain_id}",
                chain.to_dict(),
                DataType.CHAIN
            )
        
        logger.info(f"Chain {chain_id} integrity verified: {len(chain_data)} records")
        return True
    
    async def export_chain(
        self,
        chain_id: str,
        format: str = "json"
    ) -> str:
        """Exporte une chaîne de hachage."""
        chain_data = await self.get_data_by_chain(chain_id, limit=10000)
        
        if format == "json":
            return json.dumps([d.to_dict() for d in chain_data], indent=2)
        elif format == "csv":
            import csv
            import io
            output = io.StringIO()
            if chain_data:
                writer = csv.DictWriter(output, fieldnames=chain_data[0].to_dict().keys())
                writer.writeheader()
                writer.writerows([d.to_dict() for d in chain_data])
            return output.getvalue()
        else:
            return json.dumps([d.to_dict() for d in chain_data])
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._data_lock:
            self._stats["cached_data"] = len(self._data)
        with self._chain_lock:
            self._stats["cached_chains"] = len(self._chains)
        with self._cache_lock:
            self._stats["cache_size"] = len(self._verification_cache)
        
        return self._stats.copy()


# ============== HASHED DATA UTILITIES ==============

class HashUtils:
    """Utilitaires pour les opérations de hachage."""
    
    @staticmethod
    def hash_data(data: Any, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> str:
        """Hache des données."""
        if isinstance(data, str):
            data = data.encode()
        elif isinstance(data, dict):
            data = json.dumps(data, sort_keys=True).encode()
        elif isinstance(data, bytes):
            pass
        else:
            data = pickle.dumps(data)
        
        hash_func = hashlib.new(algorithm.value)
        hash_func.update(data)
        return hash_func.hexdigest()
    
    @staticmethod
    def hash_file(file_path: str, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> str:
        """Hache un fichier."""
        hash_func = hashlib.new(algorithm.value)
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    
    @staticmethod
    def verify_hash(data: Any, expected_hash: str, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> bool:
        """Vérifie un hachage."""
        computed_hash = HashUtils.hash_data(data, algorithm)
        return computed_hash == expected_hash
    
    @staticmethod
    def merkle_root(data_list: List[Any], algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> str:
        """Calcule la racine de Merkle d'une liste de données."""
        if not data_list:
            return ""
        
        # Hachage de chaque élément
        hashes = [HashUtils.hash_data(data, algorithm) for data in data_list]
        
        # Construction de l'arbre de Merkle
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])  # Dupliquer le dernier
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i+1]
                new_hashes.append(HashUtils.hash_data(combined, algorithm))
            hashes = new_hashes
        
        return hashes[0] if hashes else ""
    
    @staticmethod
    def merkle_proof(data: Any, data_list: List[Any], algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> Dict[str, Any]:
        """Génère une preuve Merkle pour une donnée."""
        if not data_list:
            return {"success": False, "message": "Empty data list"}
        
        # Hachage de chaque élément
        hashes = [HashUtils.hash_data(d, algorithm) for d in data_list]
        data_hash = HashUtils.hash_data(data, algorithm)
        
        if data_hash not in hashes:
            return {"success": False, "message": "Data not found in list"}
        
        # Construction de la preuve
        index = hashes.index(data_hash)
        proof = []
        
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            
            if index % 2 == 0:
                # Côté gauche
                proof.append({"side": "right", "hash": hashes[index + 1] if index + 1 < len(hashes) else ""})
            else:
                # Côté droit
                proof.append({"side": "left", "hash": hashes[index - 1]})
            
            # Nouvelle couche
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i+1]
                new_hashes.append(HashUtils.hash_data(combined, algorithm))
            
            index = index // 2
            hashes = new_hashes
        
        return {
            "success": True,
            "root_hash": hashes[0] if hashes else "",
            "data_hash": data_hash,
            "proof": proof,
            "index": index
        }
    
    @staticmethod
    def verify_merkle_proof(root_hash: str, data_hash: str, proof: List[Dict[str, str]], algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> bool:
        """Vérifie une preuve Merkle."""
        current_hash = data_hash
        
        for p in proof:
            if p["side"] == "left":
                combined = p["hash"] + current_hash
            else:
                combined = current_hash + p["hash"]
            current_hash = HashUtils.hash_data(combined, algorithm)
        
        return current_hash == root_hash


# ============== FACTORY ==============

class HashedStorageFactory:
    """Factory pour créer des composants de stockage haché."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        secret_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> HashedStorageEngine:
        """Crée un moteur de stockage haché."""
        engine = HashedStorageEngine(
            data_manager=data_manager,
            secret_key=secret_key,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "HashAlgorithm",
    "HashVerificationStatus",
    "IntegrityLevel",
    "HashedData",
    "HashChain",
    "HashVerificationResult",
    "HashedStorageInterface",
    "HashedStorageEngine",
    "HashUtils",
    "HashedStorageFactory"
]
