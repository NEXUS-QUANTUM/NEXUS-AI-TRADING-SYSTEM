# trading/bots/hedge_bot/hedge_bot_signer.py
# Advanced Digital Signature & Transaction Signing Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Signer Module - Module avancé de signature numérique et de signing de transactions
pour le Hedge Bot. Gère la signature cryptographique, la vérification, l'authentification
des transactions, la non-répudiation et l'intégrité des données pour l'ensemble du système.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, ed25519, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import jwt
import nacl.signing
import nacl.encoding
import nacl.secret
import nacl.utils

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_signer")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext, EncryptionKey
)


# ============== ENUMS & TYPES ==============

class SignatureAlgorithm(Enum):
    """Algorithmes de signature."""
    RSA_2048 = "rsa_2048"
    RSA_3072 = "rsa_3072"
    RSA_4096 = "rsa_4096"
    ECDSA_P256 = "ecdsa_p256"
    ECDSA_P384 = "ecdsa_p384"
    ECDSA_P521 = "ecdsa_p521"
    ED25519 = "ed25519"
    ED448 = "ed448"
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA512 = "hmac_sha512"
    ES256 = "es256"
    ES384 = "es384"
    ES512 = "es512"
    RS256 = "rs256"
    RS384 = "rs384"
    RS512 = "rs512"


class SignatureFormat(Enum):
    """Formats de signature."""
    RAW = "raw"
    BASE64 = "base64"
    HEX = "hex"
    PEM = "pem"
    DER = "der"
    JWT = "jwt"
    PKCS7 = "pkcs7"


class SignerType(Enum):
    """Types de signeur."""
    SINGLE = "single"                  # Signature unique
    MULTI = "multi"                    # Signature multiple
    THRESHOLD = "threshold"            # Signature à seuil
    TIERED = "tiered"                  # Signature hiérarchique
    CIRCLE = "circle"                  # Signature en cercle


# ============== DATA MODELS ==============

@dataclass
class SignatureKey:
    """Clé de signature."""
    key_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    algorithm: SignatureAlgorithm = SignatureAlgorithm.ED25519
    private_key: Optional[bytes] = None
    public_key: Optional[bytes] = None
    key_data: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    active: bool = True
    owner: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "key_id": self.key_id,
            "algorithm": self.algorithm.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "active": self.active,
            "owner": self.owner,
            "description": self.description,
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class SignedData:
    """Données signées."""
    signed_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data: Any = None
    signature: str = ""
    algorithm: SignatureAlgorithm = SignatureAlgorithm.ED25519
    format: SignatureFormat = SignatureFormat.BASE64
    key_id: str = ""
    signer: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    nonce: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    verified: bool = False
    verification_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "signed_id": self.signed_id,
            "data": self.data,
            "signature": self.signature,
            "algorithm": self.algorithm.value,
            "format": self.format.value,
            "key_id": self.key_id,
            "signer": self.signer,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "nonce": self.nonce,
            "metadata": self.metadata,
            "tags": self.tags,
            "verified": self.verified,
            "verification_time": self.verification_time.isoformat() if self.verification_time else None
        }


@dataclass
class MultiSignature:
    """Signature multiple."""
    multi_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_id: str = ""
    signatures: List[Dict[str, Any]] = field(default_factory=list)
    required_signatures: int = 1
    threshold: int = 1
    signer_type: SignerType = SignerType.SINGLE
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    verified: bool = False


@dataclass
class SignatureVerification:
    """Vérification de signature."""
    verification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signed_data: SignedData = field(default_factory=SignedData)
    public_key: Optional[bytes] = None
    valid: bool = False
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class SignerEngineInterface(ABC):
    """Interface abstraite pour le moteur de signature."""
    
    @abstractmethod
    async def generate_key(self, algorithm: SignatureAlgorithm) -> SignatureKey:
        """Génère une clé de signature."""
        pass
    
    @abstractmethod
    async def sign(self, data: Any, key_id: str) -> SignedData:
        """Signe des données."""
        pass
    
    @abstractmethod
    async def verify(self, signed: SignedData) -> SignatureVerification:
        """Vérifie une signature."""
        pass


# ============== IMPLÉMENTATION ==============

class SignerEngine(SignerEngineInterface):
    """
    Moteur de signature avancé pour le Hedge Bot.
    Gère la signature numérique, la vérification et l'authentification des transactions.
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
        
        # Gestion des clés
        self._keys: Dict[str, SignatureKey] = {}
        self._keys_lock = threading.RLock()
        
        # Gestion des signatures
        self._signatures: Dict[str, SignedData] = {}
        self._signatures_lock = threading.RLock()
        
        # Gestion des multi-signatures
        self._multi_signatures: Dict[str, MultiSignature] = {}
        self._multi_lock = threading.RLock()
        
        # Cache des vérifications
        self._verification_cache: Dict[str, SignatureVerification] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "keys_generated": 0,
            "signatures_created": 0,
            "signatures_verified": 0,
            "verifications_passed": 0,
            "verifications_failed": 0,
            "multi_signatures_created": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Backend
        self._backend = default_backend()
        
        # État
        self._is_running = False
        
        logger.info("SignerEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_algorithm": SignatureAlgorithm.ED25519,
            "default_format": SignatureFormat.BASE64,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "key_rotation_days": 365,
            "max_key_size": 4096,
            "jwt_issuer": "nexus_hedge_bot",
            "jwt_audience": "nexus_system",
            "nonce_length": 32,
            "signature_timeout": 300,
            "multi_signature_threshold": 0.5
        }
    
    async def start(self) -> None:
        """Démarre le moteur de signature."""
        logger.info("SignerEngine starting...")
        self._is_running = True
        
        # Chargement des clés existantes
        await self._load_keys()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("SignerEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de signature."""
        logger.info("SignerEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des clés
        await self._save_keys()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("SignerEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def generate_key(self, algorithm: SignatureAlgorithm) -> SignatureKey:
        """Génère une clé de signature."""
        self._stats["keys_generated"] += 1
        
        try:
            key = SignatureKey(
                algorithm=algorithm,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=self.config["key_rotation_days"])
            )
            
            # Génération selon l'algorithme
            if algorithm == SignatureAlgorithm.ED25519:
                private_key = nacl.signing.SigningKey.generate()
                key.private_key = private_key.encode()
                key.public_key = private_key.verify_key.encode()
            
            elif algorithm in [SignatureAlgorithm.ECDSA_P256, SignatureAlgorithm.ECDSA_P384, SignatureAlgorithm.ECDSA_P521]:
                curve = self._get_ec_curve(algorithm)
                private_key = ec.generate_private_key(curve, self._backend)
                key.private_key = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                public_key = private_key.public_key()
                key.public_key = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
            
            elif algorithm in [SignatureAlgorithm.RSA_2048, SignatureAlgorithm.RSA_3072, SignatureAlgorithm.RSA_4096]:
                key_size = self._get_rsa_key_size(algorithm)
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=key_size,
                    backend=self._backend
                )
                key.private_key = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                public_key = private_key.public_key()
                key.public_key = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
            
            elif algorithm in [SignatureAlgorithm.HMAC_SHA256, SignatureAlgorithm.HMAC_SHA512]:
                key.private_key = os.urandom(32)
                key.public_key = key.private_key
            
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            
            # Stockage de la clé
            with self._keys_lock:
                self._keys[key.key_id] = key
            
            # Stockage persistant
            if self.data_manager:
                await self.data_manager.store(
                    f"signer:key:{key.key_id}",
                    key.to_dict(),
                    DataType.KEY
                )
            
            logger.info(f"Signature key generated: {key.key_id} algorithm={algorithm.value}")
            return key
            
        except Exception as e:
            logger.error(f"Key generation error: {e}")
            raise
    
    async def sign(self, data: Any, key_id: str) -> SignedData:
        """Signe des données."""
        self._stats["signatures_created"] += 1
        
        try:
            # Récupération de la clé
            with self._keys_lock:
                key = self._keys.get(key_id)
                if not key:
                    raise ValueError(f"Key {key_id} not found")
                
                if not key.active:
                    raise ValueError(f"Key {key_id} is inactive")
                
                if key.expires_at and datetime.now(timezone.utc) > key.expires_at:
                    raise ValueError(f"Key {key_id} has expired")
            
            # Sérialisation des données
            data_bytes = self._serialize_data(data)
            
            # Génération du nonce
            nonce = base64.b64encode(os.urandom(self.config["nonce_length"])).decode()
            
            # Signature selon l'algorithme
            signature = await self._perform_signature(data_bytes, key, nonce)
            
            # Création des données signées
            signed = SignedData(
                data=data,
                signature=signature,
                algorithm=key.algorithm,
                format=self.config["default_format"],
                key_id=key.key_id,
                signer=key.owner or "system",
                nonce=nonce,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.config["signature_timeout"])
            )
            
            # Stockage de la signature
            with self._signatures_lock:
                self._signatures[signed.signed_id] = signed
            
            logger.debug(f"Data signed: {signed.signed_id} algorithm={key.algorithm.value}")
            return signed
            
        except Exception as e:
            logger.error(f"Signature error: {e}")
            raise
    
    async def verify(self, signed: SignedData) -> SignatureVerification:
        """Vérifie une signature."""
        self._stats["signatures_verified"] += 1
        
        # Vérification du cache
        cache_key = f"{signed.signed_id}_{int(time.time() / self.config['cache_ttl'])}"
        if self.config["enable_cache"] and cache_key in self._verification_cache:
            self._stats["cache_hits"] += 1
            return self._verification_cache[cache_key]
        
        self._stats["cache_misses"] += 1
        
        try:
            # Récupération de la clé
            with self._keys_lock:
                key = self._keys.get(signed.key_id)
                if not key:
                    return SignatureVerification(
                        signed_data=signed,
                        valid=False,
                        message=f"Key {signed.key_id} not found"
                    )
            
            # Vérification de l'expiration
            if signed.expires_at and datetime.now(timezone.utc) > signed.expires_at:
                return SignatureVerification(
                    signed_data=signed,
                    valid=False,
                    message="Signature has expired"
                )
            
            # Sérialisation des données
            data_bytes = self._serialize_data(signed.data)
            
            # Vérification selon l'algorithme
            valid = await self._perform_verification(data_bytes, signed, key)
            
            # Création de la vérification
            verification = SignatureVerification(
                signed_data=signed,
                valid=valid,
                message="Signature verified" if valid else "Signature verification failed"
            )
            
            # Mise à jour des statistiques
            if valid:
                self._stats["verifications_passed"] += 1
                signed.verified = True
                signed.verification_time = datetime.now(timezone.utc)
            else:
                self._stats["verifications_failed"] += 1
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._verification_cache) < self.config["cache_size"]:
                        self._verification_cache[cache_key] = verification
            
            return verification
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return SignatureVerification(
                signed_data=signed,
                valid=False,
                message=f"Verification error: {str(e)}"
            )
    
    # ========== MÉTHODES PRIVÉES - SIGNATURE ==========
    
    async def _perform_signature(self, data: bytes, key: SignatureKey, nonce: str) -> str:
        """Exécute la signature selon l'algorithme."""
        if key.algorithm in [SignatureAlgorithm.ED25519]:
            signing_key = nacl.signing.SigningKey(key.private_key)
            signature = signing_key.sign(data + nonce.encode())
            return base64.b64encode(signature.signature).decode()
        
        elif key.algorithm in [SignatureAlgorithm.ECDSA_P256, SignatureAlgorithm.ECDSA_P384, SignatureAlgorithm.ECDSA_P521]:
            private_key = serialization.load_pem_private_key(
                key.private_key,
                password=None,
                backend=self._backend
            )
            signature = private_key.sign(
                data + nonce.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            return base64.b64encode(signature).decode()
        
        elif key.algorithm in [SignatureAlgorithm.RSA_2048, SignatureAlgorithm.RSA_3072, SignatureAlgorithm.RSA_4096]:
            private_key = serialization.load_pem_private_key(
                key.private_key,
                password=None,
                backend=self._backend
            )
            signature = private_key.sign(
                data + nonce.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return base64.b64encode(signature).decode()
        
        elif key.algorithm in [SignatureAlgorithm.HMAC_SHA256]:
            signature = hmac.new(key.private_key, data + nonce.encode(), hashlib.sha256).digest()
            return base64.b64encode(signature).decode()
        
        elif key.algorithm in [SignatureAlgorithm.HMAC_SHA512]:
            signature = hmac.new(key.private_key, data + nonce.encode(), hashlib.sha512).digest()
            return base64.b64encode(signature).decode()
        
        else:
            raise ValueError(f"Unsupported algorithm for signing: {key.algorithm}")
    
    async def _perform_verification(self, data: bytes, signed: SignedData, key: SignatureKey) -> bool:
        """Exécute la vérification selon l'algorithme."""
        try:
            signature_bytes = base64.b64decode(signed.signature)
            
            if key.algorithm in [SignatureAlgorithm.ED25519]:
                verify_key = nacl.signing.VerifyKey(key.public_key)
                try:
                    verify_key.verify(data + signed.nonce.encode(), signature_bytes)
                    return True
                except nacl.exceptions.BadSignatureError:
                    return False
            
            elif key.algorithm in [SignatureAlgorithm.ECDSA_P256, SignatureAlgorithm.ECDSA_P384, SignatureAlgorithm.ECDSA_P521]:
                public_key = serialization.load_pem_public_key(
                    key.public_key,
                    backend=self._backend
                )
                try:
                    public_key.verify(
                        signature_bytes,
                        data + signed.nonce.encode(),
                        ec.ECDSA(hashes.SHA256())
                    )
                    return True
                except Exception:
                    return False
            
            elif key.algorithm in [SignatureAlgorithm.RSA_2048, SignatureAlgorithm.RSA_3072, SignatureAlgorithm.RSA_4096]:
                public_key = serialization.load_pem_public_key(
                    key.public_key,
                    backend=self._backend
                )
                try:
                    public_key.verify(
                        signature_bytes,
                        data + signed.nonce.encode(),
                        padding.PSS(
                            mgf=padding.MGF1(hashes.SHA256()),
                            salt_length=padding.PSS.MAX_LENGTH
                        ),
                        hashes.SHA256()
                    )
                    return True
                except Exception:
                    return False
            
            elif key.algorithm in [SignatureAlgorithm.HMAC_SHA256]:
                expected = hmac.new(key.private_key, data + signed.nonce.encode(), hashlib.sha256).digest()
                return hmac.compare_digest(signature_bytes, expected)
            
            elif key.algorithm in [SignatureAlgorithm.HMAC_SHA512]:
                expected = hmac.new(key.private_key, data + signed.nonce.encode(), hashlib.sha512).digest()
                return hmac.compare_digest(signature_bytes, expected)
            
            else:
                raise ValueError(f"Unsupported algorithm for verification: {key.algorithm}")
                
        except Exception as e:
            logger.debug(f"Verification error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - MULTI-SIGNATURE ==========
    
    async def create_multi_signature(
        self,
        data_id: str,
        signers: List[Tuple[str, str]],  # (key_id, signer_name)
        threshold: Optional[int] = None
    ) -> MultiSignature:
        """Crée une multi-signature."""
        required = threshold or max(1, int(len(signers) * self.config["multi_signature_threshold"]))
        
        multi = MultiSignature(
            data_id=data_id,
            required_signatures=len(signers),
            threshold=required,
            signer_type=SignerType.MULTI if len(signers) > 1 else SignerType.SINGLE,
            signatures=[]
        )
        
        with self._multi_lock:
            self._multi_signatures[multi.multi_id] = multi
            self._stats["multi_signatures_created"] += 1
        
        return multi
    
    async def add_signature_to_multi(self, multi_id: str, key_id: str, signature: str) -> bool:
        """Ajoute une signature à une multi-signature."""
        with self._multi_lock:
            multi = self._multi_signatures.get(multi_id)
            if not multi:
                return False
            
            multi.signatures.append({
                "key_id": key_id,
                "signature": signature,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            if len(multi.signatures) >= multi.threshold:
                multi.verified = True
            
            return True
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _serialize_data(self, data: Any) -> bytes:
        """Sérialise des données pour la signature."""
        if isinstance(data, str):
            return data.encode()
        elif isinstance(data, bytes):
            return data
        elif isinstance(data, dict):
            return json.dumps(data, sort_keys=True).encode()
        else:
            return json.dumps({"data": str(data)}).encode()
    
    def _get_ec_curve(self, algorithm: SignatureAlgorithm) -> ec.EllipticCurve:
        """Récupère la courbe EC pour un algorithme."""
        curves = {
            SignatureAlgorithm.ECDSA_P256: ec.SECP256R1(),
            SignatureAlgorithm.ECDSA_P384: ec.SECP384R1(),
            SignatureAlgorithm.ECDSA_P521: ec.SECP521R1()
        }
        return curves.get(algorithm, ec.SECP256R1())
    
    def _get_rsa_key_size(self, algorithm: SignatureAlgorithm) -> int:
        """Récupère la taille de clé RSA."""
        sizes = {
            SignatureAlgorithm.RSA_2048: 2048,
            SignatureAlgorithm.RSA_3072: 3072,
            SignatureAlgorithm.RSA_4096: 4096
        }
        return sizes.get(algorithm, 2048)
    
    # ========== MÉTHODES PRIVÉES - PERSISTANCE ==========
    
    async def _load_keys(self) -> None:
        """Charge les clés existantes."""
        try:
            if self.data_manager:
                keys_data = await self.data_manager.retrieve(
                    "signer:keys",
                    DataType.KEY
                )
                
                if keys_data:
                    for key_dict in keys_data:
                        key = self._deserialize_key(key_dict)
                        if key:
                            with self._keys_lock:
                                self._keys[key.key_id] = key
            
            logger.info(f"Loaded {len(self._keys)} signature keys")
            
        except Exception as e:
            logger.error(f"Load keys error: {e}")
    
    async def _save_keys(self) -> None:
        """Sauvegarde les clés."""
        try:
            if self.data_manager:
                with self._keys_lock:
                    for key in self._keys.values():
                        await self.data_manager.store(
                            f"signer:key:{key.key_id}",
                            key.to_dict(),
                            DataType.KEY
                        )
            
            logger.info("Keys saved")
            
        except Exception as e:
            logger.error(f"Save keys error: {e}")
    
    def _deserialize_key(self, data: Dict) -> Optional[SignatureKey]:
        """Désérialise une clé."""
        try:
            return SignatureKey(
                key_id=data.get("key_id", str(uuid.uuid4())),
                algorithm=SignatureAlgorithm(data.get("algorithm", "ed25519")),
                private_key=base64.b64decode(data.get("private_key")) if data.get("private_key") else None,
                public_key=base64.b64decode(data.get("public_key")) if data.get("public_key") else None,
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                expires_at=datetime.fromisoformat(data.get("expires_at")) if data.get("expires_at") else None,
                active=data.get("active", True),
                owner=data.get("owner", ""),
                description=data.get("description", ""),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", [])
            )
        except Exception as e:
            logger.error(f"Error deserializing key: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._verification_cache) > self.config["cache_size"]:
                        keys = list(self._verification_cache.keys())
                        for key in keys[:len(self._verification_cache) - self.config["cache_size"]]:
                            del self._verification_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._keys_lock:
                    self._stats["total_keys"] = len(self._keys)
                    active_keys = len([k for k in self._keys.values() if k.active])
                    self._stats["active_keys"] = active_keys
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "signer:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_key(self, key_id: str) -> Optional[SignatureKey]:
        """Récupère une clé."""
        with self._keys_lock:
            return self._keys.get(key_id)
    
    async def get_keys(self) -> List[SignatureKey]:
        """Récupère les clés."""
        with self._keys_lock:
            return list(self._keys.values())
    
    async def get_signature(self, signed_id: str) -> Optional[SignedData]:
        """Récupère une signature."""
        with self._signatures_lock:
            return self._signatures.get(signed_id)
    
    async def get_signatures(self) -> List[SignedData]:
        """Récupère les signatures."""
        with self._signatures_lock:
            return list(self._signatures.values())
    
    async def get_multi_signature(self, multi_id: str) -> Optional[MultiSignature]:
        """Récupère une multi-signature."""
        with self._multi_lock:
            return self._multi_signatures.get(multi_id)
    
    async def revoke_key(self, key_id: str) -> bool:
        """Révoque une clé."""
        with self._keys_lock:
            key = self._keys.get(key_id)
            if not key:
                return False
            
            key.active = False
            logger.info(f"Key revoked: {key_id}")
            return True
    
    async def renew_key(self, key_id: str) -> bool:
        """Renouvelle une clé."""
        with self._keys_lock:
            key = self._keys.get(key_id)
            if not key:
                return False
            
            key.expires_at = datetime.now(timezone.utc) + timedelta(days=self.config["key_rotation_days"])
            logger.info(f"Key renewed: {key_id}")
            return True
    
    async def sign_jwt(self, payload: Dict[str, Any], key_id: str) -> str:
        """Crée un JWT signé."""
        key = await self.get_key(key_id)
        if not key:
            raise ValueError(f"Key {key_id} not found")
        
        # Préparation du payload
        payload.update({
            "iat": datetime.now(timezone.utc).timestamp(),
            "exp": (datetime.now(timezone.utc) + timedelta(seconds=self.config["signature_timeout"])).timestamp(),
            "iss": self.config["jwt_issuer"],
            "aud": self.config["jwt_audience"]
        })
        
        # Sélection de l'algorithme JWT
        jwt_algorithms = {
            SignatureAlgorithm.ED25519: None,  # Non supporté par PyJWT
            SignatureAlgorithm.ECDSA_P256: "ES256",
            SignatureAlgorithm.ECDSA_P384: "ES384",
            SignatureAlgorithm.ECDSA_P521: "ES512",
            SignatureAlgorithm.RSA_2048: "RS256",
            SignatureAlgorithm.RSA_3072: "RS384",
            SignatureAlgorithm.RSA_4096: "RS512"
        }
        
        algorithm = jwt_algorithms.get(key.algorithm)
        if not algorithm:
            raise ValueError(f"Algorithm {key.algorithm.value} not supported for JWT")
        
        # Génération du JWT
        if key.algorithm in [SignatureAlgorithm.RSA_2048, SignatureAlgorithm.RSA_3072, SignatureAlgorithm.RSA_4096]:
            private_key = serialization.load_pem_private_key(
                key.private_key,
                password=None,
                backend=self._backend
            )
            token = jwt.encode(payload, private_key, algorithm=algorithm)
        elif key.algorithm in [SignatureAlgorithm.ECDSA_P256, SignatureAlgorithm.ECDSA_P384, SignatureAlgorithm.ECDSA_P521]:
            private_key = serialization.load_pem_private_key(
                key.private_key,
                password=None,
                backend=self._backend
            )
            token = jwt.encode(payload, private_key, algorithm=algorithm)
        else:
            raise ValueError(f"Algorithm {key.algorithm.value} not supported for JWT")
        
        return token
    
    async def verify_jwt(self, token: str) -> Dict[str, Any]:
        """Vérifie un JWT."""
        try:
            # Décodage sans vérification pour récupérer le key_id
            unverified = jwt.decode(token, options={"verify_signature": False})
            key_id = unverified.get("key_id")
            
            if not key_id:
                raise ValueError("No key_id in JWT")
            
            key = await self.get_key(key_id)
            if not key:
                raise ValueError(f"Key {key_id} not found")
            
            # Vérification
            if key.algorithm in [SignatureAlgorithm.RSA_2048, SignatureAlgorithm.RSA_3072, SignatureAlgorithm.RSA_4096]:
                public_key = serialization.load_pem_public_key(key.public_key, backend=self._backend)
                payload = jwt.decode(token, public_key, algorithms=["RS256", "RS384", "RS512"])
            elif key.algorithm in [SignatureAlgorithm.ECDSA_P256, SignatureAlgorithm.ECDSA_P384, SignatureAlgorithm.ECDSA_P521]:
                public_key = serialization.load_pem_public_key(key.public_key, backend=self._backend)
                payload = jwt.decode(token, public_key, algorithms=["ES256", "ES384", "ES512"])
            else:
                raise ValueError(f"Algorithm {key.algorithm.value} not supported for JWT verification")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise ValueError("JWT has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid JWT: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._keys_lock:
            self._stats["total_keys"] = len(self._keys)
        
        return self._stats.copy()


# ============== FACTORY ==============

class SignerFactory:
    """Factory pour créer des composants de signature."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SignerEngine:
        """Crée un moteur de signature."""
        engine = SignerEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "SignatureAlgorithm",
    "SignatureFormat",
    "SignerType",
    "SignatureKey",
    "SignedData",
    "MultiSignature",
    "SignatureVerification",
    "SignerEngineInterface",
    "SignerEngine",
    "SignerFactory"
]
