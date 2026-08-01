# trading/bots/hedge_bot/hedge_bot_data_licensed.py
# Advanced License Management & DRM Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Licensed Data Module - Module avancé de gestion des licences et DRM pour le Hedge Bot.
Gère les licences, l'activation, la validation, le contrôle d'utilisation, les droits d'accès
et la protection contre le piratage pour l'ensemble du système de hedging.
"""

import asyncio
import json
import time
import hashlib
import hmac
import base64
import os
import platform
import socket
import uuid as uuid_lib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import threading
import concurrent.futures
import subprocess
import re
import binascii

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_licensed")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class LicenseType(Enum):
    """Types de licences."""
    EVALUATION = "evaluation"          # Licence d'évaluation
    INDIVIDUAL = "individual"          # Licence individuelle
    TEAM = "team"                      # Licence d'équipe
    ENTERPRISE = "enterprise"          # Licence entreprise
    OEM = "oem"                        # Licence OEM
    ACADEMIC = "academic"              # Licence académique
    NON_PROFIT = "non_profit"          # Licence à but non lucratif
    CUSTOM = "custom"                  # Licence personnalisée


class LicenseFeature(Enum):
    """Fonctionnalités sous licence."""
    FULL_TRADING = "full_trading"
    PAPER_TRADING = "paper_trading"
    BACKTESTING = "backtesting"
    AI_SIGNALS = "ai_signals"
    RISK_MANAGEMENT = "risk_management"
    HEDGING = "hedging"
    OPTIONS = "options"
    FOREX = "forex"
    CRYPTO = "crypto"
    STOCKS = "stocks"
    API_ACCESS = "api_access"
    WEBHOOKS = "webhooks"
    CUSTOM_STRATEGIES = "custom_strategies"
    LIVE_TRADING = "live_trading"
    MULTI_USER = "multi_user"
    ADVANCED_ANALYTICS = "advanced_analytics"


class LicenseStatus(Enum):
    """Statuts de licence."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
    PENDING = "pending"
    TRIAL = "trial"
    GRACE = "grace"


class LicenseValidation(Enum):
    """Résultats de validation."""
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
    HARDWARE_MISMATCH = "hardware_mismatch"
    ACTIVATION_LIMIT = "activation_limit"
    CORRUPTED = "corrupted"


# ============== DATA MODELS ==============

@dataclass
class License:
    """Modèle de licence."""
    license_id: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    license_key: str = ""
    license_type: LicenseType = LicenseType.INDIVIDUAL
    features: List[LicenseFeature] = field(default_factory=list)
    status: LicenseStatus = LicenseStatus.PENDING
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=365))
    activation_count: int = 0
    max_activations: int = 1
    hardware_ids: List[str] = field(default_factory=list)
    owner: str = ""
    company: str = ""
    email: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    signature: Optional[str] = None
    public_key: Optional[str] = None
    version: int = 1
    
    def to_dict(self) -> Dict:
        return {
            "license_id": self.license_id,
            "license_key": self.license_key,
            "license_type": self.license_type.value,
            "features": [f.value for f in self.features],
            "status": self.status.value,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "activation_count": self.activation_count,
            "max_activations": self.max_activations,
            "hardware_ids": self.hardware_ids,
            "owner": self.owner,
            "company": self.company,
            "email": self.email,
            "metadata": self.metadata,
            "tags": self.tags,
            "signature": self.signature,
            "public_key": self.public_key,
            "version": self.version
        }


@dataclass
class LicenseActivation:
    """Modèle d'activation de licence."""
    activation_id: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    license_id: str = ""
    hardware_id: str = ""
    machine_name: str = ""
    os: str = ""
    hostname: str = ""
    ip_address: str = ""
    activated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_verified: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"  # active, inactive, suspended
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "activation_id": self.activation_id,
            "license_id": self.license_id,
            "hardware_id": self.hardware_id,
            "machine_name": self.machine_name,
            "os": self.os,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "activated_at": self.activated_at.isoformat(),
            "last_verified": self.last_verified.isoformat(),
            "status": self.status,
            "metadata": self.metadata
        }


@dataclass
class LicenseValidationResult:
    """Résultat de validation de licence."""
    validation_id: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    license_id: str = ""
    status: LicenseValidation = LicenseValidation.VALID
    features: List[LicenseFeature] = field(default_factory=list)
    message: str = ""
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class LicenseEngineInterface(ABC):
    """Interface abstraite pour le moteur de licences."""
    
    @abstractmethod
    async def activate_license(self, license_key: str, hardware_id: str) -> LicenseValidationResult:
        """Active une licence."""
        pass
    
    @abstractmethod
    async def validate_license(self, license_id: str) -> LicenseValidationResult:
        """Valide une licence."""
        pass
    
    @abstractmethod
    async def get_license(self, license_id: str) -> Optional[License]:
        """Récupère une licence."""
        pass


# ============== IMPLÉMENTATION ==============

class LicenseEngine(LicenseEngineInterface):
    """
    Moteur de gestion des licences avancé pour le Hedge Bot.
    Gère les licences, l'activation, la validation et le DRM.
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
        
        # Gestion des licences
        self._licenses: Dict[str, License] = {}
        self._licenses_lock = threading.RLock()
        
        # Gestion des activations
        self._activations: Dict[str, LicenseActivation] = {}
        self._activations_lock = threading.RLock()
        
        # Cache de validation
        self._validation_cache: Dict[str, LicenseValidationResult] = {}
        self._cache_lock = threading.RLock()
        
        # Hardware ID de la machine actuelle
        self._hardware_id = self._generate_hardware_id()
        
        # Licence active
        self._active_license: Optional[License] = None
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "licenses_created": 0,
            "activations_performed": 0,
            "validations_performed": 0,
            "validations_passed": 0,
            "validations_failed": 0,
            "active_licenses": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Clé secrète pour signature
        self._secret_key = os.urandom(32).hex()
        
        logger.info("LicenseEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_license_type": LicenseType.EVALUATION,
            "evaluation_days": 30,
            "grace_days": 7,
            "max_activations": 1,
            "enable_hardware_locking": True,
            "enable_online_validation": True,
            "validation_interval": 3600,
            "cache_ttl": 300,
            "enable_cache": True,
            "signature_required": True,
            "license_server_url": "https://licensing.nexusquantum.com",
            "api_key": "",
            "auto_renew": False,
            "require_online_activation": True
        }
    
    async def start(self) -> None:
        """Démarre le moteur de licences."""
        logger.info("LicenseEngine starting...")
        self._is_running = True
        
        # Chargement des licences existantes
        await self._load_licenses()
        
        # Chargement de la licence active
        await self._load_active_license()
        
        # Validation de la licence active
        if self._active_license:
            validation = await self.validate_license(self._active_license.license_id)
            if validation.status != LicenseValidation.VALID:
                logger.warning(f"Active license invalid: {validation.message}")
                self._active_license = None
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._validation_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("LicenseEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de licences."""
        logger.info("LicenseEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("LicenseEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def activate_license(self, license_key: str, hardware_id: str) -> LicenseValidationResult:
        """Active une licence."""
        self._stats["activations_performed"] += 1
        
        try:
            # Vérification de la clé
            license_obj = await self._find_license_by_key(license_key)
            if not license_obj:
                return LicenseValidationResult(
                    status=LicenseValidation.INVALID,
                    message="License key not found"
                )
            
            # Vérification du statut
            if license_obj.status == LicenseStatus.EXPIRED:
                return LicenseValidationResult(
                    status=LicenseValidation.EXPIRED,
                    message="License has expired"
                )
            
            if license_obj.status == LicenseStatus.REVOKED:
                return LicenseValidationResult(
                    status=LicenseValidation.REVOKED,
                    message="License has been revoked"
                )
            
            if license_obj.status == LicenseStatus.SUSPENDED:
                return LicenseValidationResult(
                    status=LicenseValidation.SUSPENDED,
                    message="License has been suspended"
                )
            
            # Vérification du nombre d'activations
            if license_obj.activation_count >= license_obj.max_activations:
                return LicenseValidationResult(
                    status=LicenseValidation.ACTIVATION_LIMIT,
                    message=f"Activation limit reached: {license_obj.activation_count}/{license_obj.max_activations}"
                )
            
            # Vérification du hardware ID
            if self.config["enable_hardware_locking"]:
                if license_obj.hardware_ids and hardware_id not in license_obj.hardware_ids:
                    return LicenseValidationResult(
                        status=LicenseValidation.HARDWARE_MISMATCH,
                        message="Hardware ID mismatch"
                    )
            
            # Création de l'activation
            activation = LicenseActivation(
                license_id=license_obj.license_id,
                hardware_id=hardware_id,
                machine_name=platform.node(),
                os=platform.system(),
                hostname=socket.gethostname(),
                ip_address=socket.gethostbyname(socket.gethostname())
            )
            
            with self._activations_lock:
                self._activations[activation.activation_id] = activation
            
            # Mise à jour de la licence
            license_obj.activation_count += 1
            license_obj.status = LicenseStatus.ACTIVE
            license_obj.hardware_ids.append(hardware_id)
            
            # Mise à jour de la licence active
            self._active_license = license_obj
            
            # Sauvegarde
            await self._save_license(license_obj)
            
            # Création du résultat
            result = LicenseValidationResult(
                license_id=license_obj.license_id,
                status=LicenseValidation.VALID,
                features=license_obj.features,
                message="License activated successfully",
                metadata={
                    "activation_id": activation.activation_id,
                    "hardware_id": hardware_id
                }
            )
            
            self._stats["active_licenses"] += 1
            
            logger.info(f"License activated: {license_key} (id={license_obj.license_id})")
            return result
            
        except Exception as e:
            logger.error(f"License activation error: {e}")
            return LicenseValidationResult(
                status=LicenseValidation.INVALID,
                message=f"Activation failed: {str(e)}"
            )
    
    async def validate_license(self, license_id: str) -> LicenseValidationResult:
        """Valide une licence."""
        self._stats["validations_performed"] += 1
        
        # Vérification du cache
        cache_key = f"{license_id}_{int(time.time() / self.config['cache_ttl'])}"
        if self.config["enable_cache"] and cache_key in self._validation_cache:
            return self._validation_cache[cache_key]
        
        # Récupération de la licence
        with self._licenses_lock:
            license_obj = self._licenses.get(license_id)
            if not license_obj:
                return LicenseValidationResult(
                    status=LicenseValidation.INVALID,
                    message="License not found"
                )
        
        # Vérification du statut
        if license_obj.status == LicenseStatus.EXPIRED:
            result = LicenseValidationResult(
                status=LicenseValidation.EXPIRED,
                message="License has expired"
            )
        elif license_obj.status == LicenseStatus.REVOKED:
            result = LicenseValidationResult(
                status=LicenseValidation.REVOKED,
                message="License has been revoked"
            )
        elif license_obj.status == LicenseStatus.SUSPENDED:
            result = LicenseValidationResult(
                status=LicenseValidation.SUSPENDED,
                message="License has been suspended"
            )
        elif license_obj.status == LicenseStatus.ACTIVE:
            # Vérification de l'expiration
            if datetime.now(timezone.utc) > license_obj.expires_at:
                license_obj.status = LicenseStatus.EXPIRED
                await self._save_license(license_obj)
                result = LicenseValidationResult(
                    status=LicenseValidation.EXPIRED,
                    message="License has expired"
                )
            else:
                result = LicenseValidationResult(
                    status=LicenseValidation.VALID,
                    features=license_obj.features,
                    message="License is valid"
                )
        else:
            result = LicenseValidationResult(
                status=LicenseValidation.INVALID,
                message=f"Invalid license status: {license_obj.status.value}"
            )
        
        # Mise à jour des statistiques
        if result.status == LicenseValidation.VALID:
            self._stats["validations_passed"] += 1
        else:
            self._stats["validations_failed"] += 1
        
        # Mise en cache
        if self.config["enable_cache"]:
            with self._cache_lock:
                self._validation_cache[cache_key] = result
        
        return result
    
    async def get_license(self, license_id: str) -> Optional[License]:
        """Récupère une licence."""
        with self._licenses_lock:
            return self._licenses.get(license_id)
    
    # ========== MÉTHODES PRIVÉES - HARDWARE ==========
    
    def _generate_hardware_id(self) -> str:
        """Génère un identifiant matériel unique."""
        # Collecte des informations système
        components = [
            platform.node(),
            platform.processor(),
            platform.machine(),
            platform.system(),
            platform.release(),
            socket.gethostname()
        ]
        
        # Tentative de récupération du MAC address
        try:
            import uuid as uuid_lib
            mac = uuid_lib.getnode()
            components.append(str(mac))
        except:
            pass
        
        # Tentative de récupération du CPU ID
        try:
            if platform.system() == "Windows":
                output = subprocess.check_output("wmic cpu get processorid", shell=True).decode()
                cpu_id = re.search(r"([A-F0-9]+)", output)
                if cpu_id:
                    components.append(cpu_id.group(1))
            elif platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "serial" in line.lower():
                            components.append(line.split(":")[1].strip())
                            break
        except:
            pass
        
        # Hachage
        combined = "".join(components)
        return hashlib.sha256(combined.encode()).hexdigest()
    
    # ========== MÉTHODES PRIVÉES - LICENCES ==========
    
    async def _find_license_by_key(self, license_key: str) -> Optional[License]:
        """Trouve une licence par sa clé."""
        with self._licenses_lock:
            for license_obj in self._licenses.values():
                if license_obj.license_key == license_key:
                    return license_obj
        return None
    
    async def _create_license(self, config: Dict[str, Any]) -> License:
        """Crée une nouvelle licence."""
        license_obj = License(
            license_key=config.get("license_key", self._generate_license_key()),
            license_type=LicenseType(config.get("license_type", "evaluation")),
            features=[LicenseFeature(f) for f in config.get("features", [])],
            max_activations=config.get("max_activations", 1),
            owner=config.get("owner", ""),
            company=config.get("company", ""),
            email=config.get("email", ""),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        # Durée de validité
        if license_obj.license_type == LicenseType.EVALUATION:
            license_obj.expires_at = datetime.now(timezone.utc) + timedelta(
                days=self.config["evaluation_days"]
            )
        
        # Signature
        if self.config["signature_required"]:
            license_obj.signature = await self._sign_license(license_obj)
        
        with self._licenses_lock:
            self._licenses[license_obj.license_id] = license_obj
            self._stats["licenses_created"] += 1
        
        return license_obj
    
    def _generate_license_key(self) -> str:
        """Génère une clé de licence."""
        # Format: XXXX-XXXX-XXXX-XXXX
        parts = []
        for _ in range(4):
            part = hashlib.md5(os.urandom(8)).hexdigest()[:4].upper()
            parts.append(part)
        return "-".join(parts)
    
    async def _sign_license(self, license_obj: License) -> str:
        """Signe une licence."""
        data = f"{license_obj.license_id}{license_obj.license_key}{license_obj.expires_at.isoformat()}{license_obj.owner}"
        signature = hmac.new(
            self._secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def _verify_signature(self, license_obj: License) -> bool:
        """Vérifie la signature d'une licence."""
        if not license_obj.signature:
            return False
        
        expected = await self._sign_license(license_obj)
        return hmac.compare_digest(license_obj.signature, expected)
    
    # ========== MÉTHODES PRIVÉES - PERSISTANCE ==========
    
    async def _load_licenses(self) -> None:
        """Charge les licences existantes."""
        try:
            if self.data_manager:
                licenses_data = await self.data_manager.retrieve(
                    "license:all",
                    DataType.CONFIG
                )
                
                if licenses_data:
                    for license_dict in licenses_data:
                        license_obj = self._deserialize_license(license_dict)
                        if license_obj:
                            with self._licenses_lock:
                                self._licenses[license_obj.license_id] = license_obj
            
            logger.info(f"Loaded {len(self._licenses)} licenses")
            
        except Exception as e:
            logger.error(f"Load licenses error: {e}")
    
    async def _load_active_license(self) -> None:
        """Charge la licence active."""
        try:
            if self.data_manager:
                active_id = await self.data_manager.retrieve(
                    "license:active",
                    DataType.CONFIG
                )
                
                if active_id:
                    with self._licenses_lock:
                        self._active_license = self._licenses.get(active_id)
            
        except Exception as e:
            logger.error(f"Load active license error: {e}")
    
    async def _save_license(self, license_obj: License) -> None:
        """Sauvegarde une licence."""
        try:
            if self.data_manager:
                await self.data_manager.store(
                    f"license:{license_obj.license_id}",
                    license_obj.to_dict(),
                    DataType.CONFIG
                )
                
                # Sauvegarde de la licence active
                if self._active_license and self._active_license.license_id == license_obj.license_id:
                    await self.data_manager.store(
                        "license:active",
                        license_obj.license_id,
                        DataType.CONFIG
                    )
            
        except Exception as e:
            logger.error(f"Save license error: {e}")
    
    def _deserialize_license(self, data: Dict) -> Optional[License]:
        """Désérialise une licence."""
        try:
            return License(
                license_id=data.get("license_id", str(uuid_lib.uuid4())),
                license_key=data.get("license_key", ""),
                license_type=LicenseType(data.get("license_type", "individual")),
                features=[LicenseFeature(f) for f in data.get("features", [])],
                status=LicenseStatus(data.get("status", "pending")),
                issued_at=datetime.fromisoformat(data.get("issued_at", datetime.now(timezone.utc).isoformat())),
                expires_at=datetime.fromisoformat(data.get("expires_at", datetime.now(timezone.utc).isoformat())),
                activation_count=data.get("activation_count", 0),
                max_activations=data.get("max_activations", 1),
                hardware_ids=data.get("hardware_ids", []),
                owner=data.get("owner", ""),
                company=data.get("company", ""),
                email=data.get("email", ""),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                signature=data.get("signature"),
                public_key=data.get("public_key"),
                version=data.get("version", 1)
            )
        except Exception as e:
            logger.error(f"Error deserializing license: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _validation_loop(self) -> None:
        """Boucle de validation périodique."""
        while self._is_running:
            await asyncio.sleep(self.config["validation_interval"])
            
            try:
                if self._active_license:
                    result = await self.validate_license(self._active_license.license_id)
                    if result.status != LicenseValidation.VALID:
                        logger.warning(f"License validation failed: {result.message}")
                        self._active_license = None
                
            except Exception as e:
                logger.error(f"Validation loop error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    # Suppression des entrées de cache expirées
                    current_time = int(time.time())
                    for key in list(self._validation_cache.keys()):
                        try:
                            timestamp = int(key.split("_")[1])
                            if current_time - timestamp > self.config["cache_ttl"]:
                                del self._validation_cache[key]
                        except:
                            continue
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._licenses_lock:
                    self._stats["total_licenses"] = len(self._licenses)
                    active_licenses = len([l for l in self._licenses.values() if l.status == LicenseStatus.ACTIVE])
                    self._stats["active_licenses"] = active_licenses
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "license:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_licenses(self, status: Optional[LicenseStatus] = None) -> List[License]:
        """Récupère les licences."""
        with self._licenses_lock:
            licenses = list(self._licenses.values())
            if status:
                licenses = [l for l in licenses if l.status == status]
            return licenses
    
    async def get_activations(self, license_id: str) -> List[LicenseActivation]:
        """Récupère les activations d'une licence."""
        with self._activations_lock:
            return [a for a in self._activations.values() if a.license_id == license_id]
    
    async def get_active_license(self) -> Optional[License]:
        """Récupère la licence active."""
        return self._active_license
    
    async def create_license(self, config: Dict[str, Any]) -> License:
        """Crée une nouvelle licence."""
        license_obj = await self._create_license(config)
        await self._save_license(license_obj)
        return license_obj
    
    async def revoke_license(self, license_id: str) -> bool:
        """Révoque une licence."""
        with self._licenses_lock:
            license_obj = self._licenses.get(license_id)
            if not license_obj:
                return False
            
            license_obj.status = LicenseStatus.REVOKED
            await self._save_license(license_obj)
            
            if self._active_license and self._active_license.license_id == license_id:
                self._active_license = None
        
        logger.info(f"License revoked: {license_id}")
        return True
    
    async def renew_license(self, license_id: str, days: int = 365) -> bool:
        """Renouvelle une licence."""
        with self._licenses_lock:
            license_obj = self._licenses.get(license_id)
            if not license_obj:
                return False
            
            license_obj.expires_at = datetime.now(timezone.utc) + timedelta(days=days)
            license_obj.status = LicenseStatus.ACTIVE
            await self._save_license(license_obj)
        
        logger.info(f"License renewed: {license_id} +{days} days")
        return True
    
    async def check_feature(self, feature: LicenseFeature) -> bool:
        """Vérifie si une fonctionnalité est disponible."""
        if not self._active_license:
            return False
        
        return feature in self._active_license.features
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._licenses_lock:
            self._stats["total_licenses"] = len(self._licenses)
            active = len([l for l in self._licenses.values() if l.status == LicenseStatus.ACTIVE])
            self._stats["active_licenses"] = active
        
        return self._stats.copy()


# ============== FACTORY ==============

class LicenseFactory:
    """Factory pour créer des composants de licences."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LicenseEngine:
        """Crée un moteur de licences."""
        engine = LicenseEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "LicenseType",
    "LicenseFeature",
    "LicenseStatus",
    "LicenseValidation",
    "License",
    "LicenseActivation",
    "LicenseValidationResult",
    "LicenseEngineInterface",
    "LicenseEngine",
    "LicenseFactory"
]
