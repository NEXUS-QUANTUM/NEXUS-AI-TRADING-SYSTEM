# trading/bots/hedge_bot/hedge_bot_data_encryption.py
# Advanced Data Encryption & Security Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Encryption Module - Module de chiffrement et sécurité avancé pour le Hedge Bot.
Assure la protection des données sensibles, le chiffrement des communications, la gestion des clés
et la conformité avec les standards de sécurité les plus stricts.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import struct
import time
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import zlib
from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import constant_time
import jwt
import nacl.secret
import nacl.utils
import nacl.pwhash
import nacl.signing
import nacl.encoding
import argon2

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_encryption")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class EncryptionAlgorithm(Enum):
    """Algorithmes de chiffrement disponibles."""
    AES_256_GCM = "aes-256-gcm"
    AES_256_CBC = "aes-256-cbc"
    AES_256_CTR = "aes-256-ctr"
    CHACHA20_POLY1305 = "chacha20-poly1305"
    RSA_4096 = "rsa-4096"
    RSA_2048 = "rsa-2048"
    ECDSA_P256 = "ecdsa-p256"
    ECDSA_P384 = "ecdsa-p384"
    ECDH_P256 = "ecdh-p256"
    ECDH_P384 = "ecdh-p384"
    X25519 = "x25519"
    X448 = "x448"


class KeyDerivation(Enum):
    """Algorithmes de dérivation de clés."""
    PBKDF2 = "pbkdf2"
    HKDF = "hkdf"
    ARGON2 = "argon2"
    SCRYPT = "scrypt"
    BCRYPT = "bcrypt"


class DataClass(Enum):
    """Classifications des données."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"
    TOP_SECRET = "top_secret"
    RESTRICTED = "restricted"


class EncryptionScope(Enum):
    """Portées du chiffrement."""
    REST = "rest"
    TRANSIT = "transit"
    BOTH = "both"
    APPLICATION = "application"
    FIELD = "field"
    DATABASE = "database"
    FILE = "file"


# ============== DATA MODELS ==============

@dataclass
class EncryptionKey:
    """Modèle de clé de chiffrement."""
    key_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key_type: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    key_data: bytes = b""
    key_material: Optional[Dict[str, Any]] = None
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    active: bool = True
    scope: EncryptionScope = EncryptionScope.BOTH
    data_class: DataClass = DataClass.CONFIDENTIAL
    owner: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "key_id": self.key_id,
            "key_type": self.key_type.value,
            "key_data": base64.b64encode(self.key_data).decode() if self.key_data else None,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "active": self.active,
            "scope": self.scope.value,
            "data_class": self.data_class.value,
            "owner": self.owner,
            "description": self.description,
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class EncryptedData:
    """Modèle de données chiffrées."""
    encrypted_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key_id: str = ""
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    ciphertext: bytes = b""
    iv: Optional[bytes] = None
    salt: Optional[bytes] = None
    tag: Optional[bytes] = None
    data_class: DataClass = DataClass.CONFIDENTIAL
    scope: EncryptionScope = EncryptionScope.BOTH
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[bytes] = None
    signer_id: Optional[str] = None
    integrity_hash: Optional[str] = None
    version: int = 1
    
    def to_dict(self) -> Dict:
        return {
            "encrypted_id": self.encrypted_id,
            "key_id": self.key_id,
            "algorithm": self.algorithm.value,
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "iv": base64.b64encode(self.iv).decode() if self.iv else None,
            "salt": base64.b64encode(self.salt).decode() if self.salt else None,
            "tag": base64.b64encode(self.tag).decode() if self.tag else None,
            "data_class": self.data_class.value,
            "scope": self.scope.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
            "signature": base64.b64encode(self.signature).decode() if self.signature else None,
            "signer_id": self.signer_id,
            "integrity_hash": self.integrity_hash,
            "version": self.version
        }


@dataclass
class SecurityPolicy:
    """Modèle de politique de sécurité."""
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    data_class: DataClass = DataClass.CONFIDENTIAL
    encryption_required: bool = True
    key_rotation_days: int = 90
    min_key_length: int = 256
    allowed_algorithms: List[EncryptionAlgorithm] = field(default_factory=list)
    required_signing: bool = False
    audit_required: bool = True
    retention_days: int = 365
    allowed_scopes: List[EncryptionScope] = field(default_factory=list)
    expiration_days: int = 365
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "data_class": self.data_class.value,
            "encryption_required": self.encryption_required,
            "key_rotation_days": self.key_rotation_days,
            "min_key_length": self.min_key_length,
            "allowed_algorithms": [a.value for a in self.allowed_algorithms],
            "required_signing": self.required_signing,
            "audit_required": self.audit_required,
            "retention_days": self.retention_days,
            "allowed_scopes": [s.value for s in self.allowed_scopes],
            "expiration_days": self.expiration_days,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active": self.active
        }


@dataclass
class AuditLog:
    """Modèle de log d'audit."""
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    action: str = ""
    user: str = ""
    resource_type: str = ""
    resource_id: str = ""
    data_class: DataClass = DataClass.CONFIDENTIAL
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "user": self.user,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "data_class": self.data_class.value,
            "details": self.details,
            "success": self.success,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "signature": self.signature
        }


# ============== INTERFACES ==============

class EncryptionEngineInterface(ABC):
    """Interface abstraite pour le moteur de chiffrement."""
    
    @abstractmethod
    async def encrypt(self, data: bytes, key_id: Optional[str] = None) -> EncryptedData:
        """Chiffre des données."""
        pass
    
    @abstractmethod
    async def decrypt(self, encrypted: EncryptedData) -> bytes:
        """Déchiffre des données."""
        pass
    
    @abstractmethod
    async def sign(self, data: bytes, key_id: Optional[str] = None) -> bytes:
        """Signe des données."""
        pass
    
    @abstractmethod
    async def verify(self, data: bytes, signature: bytes, key_id: str) -> bool:
        """Vérifie une signature."""
        pass


class KeyManagementInterface(ABC):
    """Interface abstraite pour la gestion des clés."""
    
    @abstractmethod
    async def generate_key(self, algorithm: EncryptionAlgorithm) -> EncryptionKey:
        """Génère une nouvelle clé."""
        pass
    
    @abstractmethod
    async def rotate_key(self, key_id: str) -> EncryptionKey:
        """Rote une clé."""
        pass
    
    @abstractmethod
    async def get_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Récupère une clé."""
        pass


# ============== IMPLÉMENTATIONS ==============

class EncryptionEngine(EncryptionEngineInterface):
    """
    Moteur de chiffrement avancé avec support de multiples algorithmes,
    gestion des clés, signatures et vérification d'intégrité.
    """
    
    def __init__(
        self,
        key_manager: Optional[KeyManagementInterface] = None,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.key_manager = key_manager
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Cache des clés
        self._key_cache: Dict[str, EncryptionKey] = {}
        self._key_cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "encrypts": 0,
            "decrypts": 0,
            "signs": 0,
            "verifies": 0,
            "errors": 0,
            "key_cache_hits": 0,
            "key_cache_misses": 0
        }
        
        # Argon2 pour la dérivation
        self._argon2 = argon2.PasswordHasher(
            time_cost=2,
            memory_cost=19 * 1024,
            parallelism=1,
            hash_len=32,
            salt_len=16
        )
        
        # Backend
        self._backend = default_backend()
        
        logger.info("EncryptionEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "default_algorithm": EncryptionAlgorithm.AES_256_GCM,
            "default_key_id": None,
            "enable_caching": True,
            "cache_ttl": 3600,  # 1 heure
            "max_cache_size": 1000,
            "compression": True,
            "compression_level": 6,
            "key_derivation": {
                "algorithm": KeyDerivation.HKDF,
                "iterations": 100000,
                "salt_size": 32
            }
        }
    
    async def encrypt(self, data: bytes, key_id: Optional[str] = None) -> EncryptedData:
        """Chiffre des données avec chiffrement authentifié."""
        start_time = time.time()
        self._stats["encrypts"] += 1
        
        try:
            # Compression optionnelle
            if self.config["compression"] and len(data) > 1024:
                data = zlib.compress(data, self.config["compression_level"])
            
            # Sélection de la clé
            key = await self._get_key(key_id)
            if not key:
                raise ValueError(f"Key {key_id} not found")
            
            # Génération de l'IV
            iv = os.urandom(12)  # Pour GCM
            
            # Chiffrement selon l'algorithme
            if key.key_type == EncryptionAlgorithm.AES_256_GCM:
                ciphertext, tag = await self._encrypt_aes_gcm(data, key.key_data, iv)
            elif key.key_type == EncryptionAlgorithm.AES_256_CBC:
                ciphertext = await self._encrypt_aes_cbc(data, key.key_data, iv)
                tag = None
            elif key.key_type == EncryptionAlgorithm.AES_256_CTR:
                ciphertext = await self._encrypt_aes_ctr(data, key.key_data, iv)
                tag = None
            elif key.key_type == EncryptionAlgorithm.CHACHA20_POLY1305:
                ciphertext, tag = await self._encrypt_chacha20(data, key.key_data, iv)
            elif key.key_type in [EncryptionAlgorithm.RSA_2048, EncryptionAlgorithm.RSA_4096]:
                ciphertext = await self._encrypt_rsa(data, key)
                iv = None
                tag = None
            else:
                # Fallback AES-256-GCM
                ciphertext, tag = await self._encrypt_aes_gcm(data, key.key_data, iv)
            
            # Création de l'objet chiffré
            encrypted = EncryptedData(
                key_id=key.key_id,
                algorithm=key.key_type,
                ciphertext=ciphertext,
                iv=iv,
                tag=tag,
                data_class=key.data_class,
                scope=key.scope,
                created_at=datetime.now(timezone.utc),
                expires_at=key.expires_at,
                metadata={
                    "encryption_time_ms": (time.time() - start_time) * 1000,
                    "original_size": len(data)
                }
            )
            
            # Signature optionnelle
            if self.config.get("sign_encrypted", False):
                encrypted.signature = await self.sign(
                    ciphertext + (iv or b"") + (tag or b""),
                    self.config.get("signing_key_id")
                )
                encrypted.signer_id = self.config.get("signing_key_id")
            
            return encrypted
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Encryption error: {e}")
            raise
    
    async def decrypt(self, encrypted: EncryptedData) -> bytes:
        """Déchiffre des données avec vérification d'intégrité."""
        start_time = time.time()
        self._stats["decrypts"] += 1
        
        try:
            # Vérification de la signature
            if encrypted.signature and encrypted.signer_id:
                valid = await self.verify(
                    encrypted.ciphertext + (encrypted.iv or b"") + (encrypted.tag or b""),
                    encrypted.signature,
                    encrypted.signer_id
                )
                if not valid:
                    raise ValueError("Invalid signature")
            
            # Récupération de la clé
            key = await self._get_key(encrypted.key_id)
            if not key:
                raise ValueError(f"Key {encrypted.key_id} not found")
            
            # Déchiffrement selon l'algorithme
            if encrypted.algorithm == EncryptionAlgorithm.AES_256_GCM:
                data = await self._decrypt_aes_gcm(
                    encrypted.ciphertext,
                    key.key_data,
                    encrypted.iv or b"",
                    encrypted.tag or b""
                )
            elif encrypted.algorithm == EncryptionAlgorithm.AES_256_CBC:
                data = await self._decrypt_aes_cbc(
                    encrypted.ciphertext,
                    key.key_data,
                    encrypted.iv or b""
                )
            elif encrypted.algorithm == EncryptionAlgorithm.AES_256_CTR:
                data = await self._decrypt_aes_ctr(
                    encrypted.ciphertext,
                    key.key_data,
                    encrypted.iv or b""
                )
            elif encrypted.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                data = await self._decrypt_chacha20(
                    encrypted.ciphertext,
                    key.key_data,
                    encrypted.iv or b"",
                    encrypted.tag or b""
                )
            elif encrypted.algorithm in [EncryptionAlgorithm.RSA_2048, EncryptionAlgorithm.RSA_4096]:
                data = await self._decrypt_rsa(encrypted.ciphertext, key)
            else:
                raise ValueError(f"Unsupported algorithm: {encrypted.algorithm}")
            
            # Décompression
            if self.config["compression"]:
                try:
                    data = zlib.decompress(data)
                except zlib.error:
                    # Pas compressé
                    pass
            
            # Mise à jour des métadonnées
            encrypted.metadata["decryption_time_ms"] = (time.time() - start_time) * 1000
            
            return data
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Decryption error: {e}")
            raise
    
    async def sign(self, data: bytes, key_id: Optional[str] = None) -> bytes:
        """Signe des données avec une clé asymétrique."""
        self._stats["signs"] += 1
        
        try:
            key = await self._get_key(key_id)
            if not key:
                raise ValueError(f"Signing key {key_id} not found")
            
            # Signature selon le type de clé
            if key.key_type in [EncryptionAlgorithm.ECDSA_P256, EncryptionAlgorithm.ECDSA_P384]:
                return await self._sign_ecdsa(data, key)
            elif key.key_type in [EncryptionAlgorithm.RSA_2048, EncryptionAlgorithm.RSA_4096]:
                return await self._sign_rsa(data, key)
            elif key.key_type in [EncryptionAlgorithm.X25519, EncryptionAlgorithm.X448]:
                return await self._sign_ed25519(data, key)
            else:
                # HMAC par défaut
                return hmac.new(
                    key.key_data,
                    data,
                    hashlib.sha256
                ).digest()
                
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Signing error: {e}")
            raise
    
    async def verify(self, data: bytes, signature: bytes, key_id: str) -> bool:
        """Vérifie une signature."""
        self._stats["verifies"] += 1
        
        try:
            key = await self._get_key(key_id)
            if not key:
                return False
            
            # Vérification selon le type de clé
            if key.key_type in [EncryptionAlgorithm.ECDSA_P256, EncryptionAlgorithm.ECDSA_P384]:
                return await self._verify_ecdsa(data, signature, key)
            elif key.key_type in [EncryptionAlgorithm.RSA_2048, EncryptionAlgorithm.RSA_4096]:
                return await self._verify_rsa(data, signature, key)
            elif key.key_type in [EncryptionAlgorithm.X25519, EncryptionAlgorithm.X448]:
                return await self._verify_ed25519(data, signature, key)
            else:
                # HMAC par défaut
                expected = hmac.new(
                    key.key_data,
                    data,
                    hashlib.sha256
                ).digest()
                return constant_time.bytes_eq(signature, expected)
                
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Verification error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - CHIFFREMENT ==========
    
    async def _encrypt_aes_gcm(self, data: bytes, key: bytes, iv: bytes) -> Tuple[bytes, bytes]:
        """Chiffrement AES-256-GCM."""
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=self._backend
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        tag = encryptor.tag
        return ciphertext, tag
    
    async def _decrypt_aes_gcm(self, ciphertext: bytes, key: bytes, iv: bytes, tag: bytes) -> bytes:
        """Déchiffrement AES-256-GCM."""
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=self._backend
        )
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    async def _encrypt_aes_cbc(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        """Chiffrement AES-256-CBC."""
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=self._backend
        )
        encryptor = cipher.encryptor()
        return encryptor.update(padded_data) + encryptor.finalize()
    
    async def _decrypt_aes_cbc(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Déchiffrement AES-256-CBC."""
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=self._backend
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()
    
    async def _encrypt_aes_ctr(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        """Chiffrement AES-256-CTR."""
        cipher = Cipher(
            algorithms.AES(key),
            modes.CTR(iv),
            backend=self._backend
        )
        encryptor = cipher.encryptor()
        return encryptor.update(data) + encryptor.finalize()
    
    async def _decrypt_aes_ctr(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Déchiffrement AES-256-CTR."""
        cipher = Cipher(
            algorithms.AES(key),
            modes.CTR(iv),
            backend=self._backend
        )
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    async def _encrypt_chacha20(self, data: bytes, key: bytes, iv: bytes) -> Tuple[bytes, bytes]:
        """Chiffrement ChaCha20-Poly1305."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
            cipher = ChaCha20Poly1305(key)
            ciphertext = cipher.encrypt(iv, data, None)
            # Le dernier 16 bytes est le tag
            tag = ciphertext[-16:]
            ciphertext = ciphertext[:-16]
            return ciphertext, tag
        except ImportError:
            # Fallback avec sodium
            box = nacl.secret.SecretBox(key)
            encrypted = box.encrypt(data, iv[:24])
            return encrypted.ciphertext, encrypted.mac
    
    async def _decrypt_chacha20(self, ciphertext: bytes, key: bytes, iv: bytes, tag: bytes) -> bytes:
        """Déchiffrement ChaCha20-Poly1305."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
            cipher = ChaCha20Poly1305(key)
            return cipher.decrypt(iv, ciphertext + tag, None)
        except ImportError:
            # Fallback avec sodium
            box = nacl.secret.SecretBox(key)
            return box.decrypt(ciphertext + tag)
    
    async def _encrypt_rsa(self, data: bytes, key: EncryptionKey) -> bytes:
        """Chiffrement RSA."""
        private_key = serialization.load_pem_private_key(
            key.key_data,
            password=None,
            backend=self._backend
        )
        
        # Chiffrement avec la clé publique
        public_key = private_key.public_key()
        
        # Limitation de taille pour RSA
        max_size = 190  # pour RSA-2048
        if key.key_type == EncryptionAlgorithm.RSA_4096:
            max_size = 446
        
        if len(data) > max_size:
            # Chiffrement hybride: AES + RSA
            session_key = os.urandom(32)
            encrypted_session_key = public_key.encrypt(
                session_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            iv = os.urandom(12)
            encrypted_data, tag = await self._encrypt_aes_gcm(data, session_key, iv)
            
            # Format: [encrypted_session_key][iv][tag][encrypted_data]
            result = encrypted_session_key + iv + tag + encrypted_data
            return result
        
        else:
            # Chiffrement direct RSA
            return public_key.encrypt(
                data,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
    
    async def _decrypt_rsa(self, ciphertext: bytes, key: EncryptionKey) -> bytes:
        """Déchiffrement RSA."""
        private_key = serialization.load_pem_private_key(
            key.key_data,
            password=None,
            backend=self._backend
        )
        
        # Détection du mode hybride
        if len(ciphertext) > 256:  # RSA-2048 ou plus
            # Format hybride: [encrypted_session_key][iv][tag][encrypted_data]
            key_size = 256  # RSA-2048
            if key.key_type == EncryptionAlgorithm.RSA_4096:
                key_size = 512
            
            encrypted_session_key = ciphertext[:key_size]
            iv = ciphertext[key_size:key_size + 12]
            tag = ciphertext[key_size + 12:key_size + 28]
            encrypted_data = ciphertext[key_size + 28:]
            
            # Déchiffrement de la clé de session
            session_key = private_key.decrypt(
                encrypted_session_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Déchiffrement des données
            return await self._decrypt_aes_gcm(encrypted_data, session_key, iv, tag)
        
        else:
            # Déchiffrement direct RSA
            return private_key.decrypt(
                ciphertext,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
    
    # ========== MÉTHODES PRIVÉES - SIGNATURES ==========
    
    async def _sign_rsa(self, data: bytes, key: EncryptionKey) -> bytes:
        """Signature RSA."""
        private_key = serialization.load_pem_private_key(
            key.key_data,
            password=None,
            backend=self._backend
        )
        
        return private_key.sign(
            data,
            asym_padding.PSS(
                mgf=asym_padding.MGF1(hashes.SHA256()),
                salt_length=asym_padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
    
    async def _verify_rsa(self, data: bytes, signature: bytes, key: EncryptionKey) -> bool:
        """Vérification RSA."""
        public_key = serialization.load_pem_public_key(
            key.key_data,
            backend=self._backend
        )
        
        try:
            public_key.verify(
                signature,
                data,
                asym_padding.PSS(
                    mgf=asym_padding.MGF1(hashes.SHA256()),
                    salt_length=asym_padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
    
    async def _sign_ecdsa(self, data: bytes, key: EncryptionKey) -> bytes:
        """Signature ECDSA."""
        private_key = serialization.load_pem_private_key(
            key.key_data,
            password=None,
            backend=self._backend
        )
        
        return private_key.sign(
            data,
            ec.ECDSA(hashes.SHA256())
        )
    
    async def _verify_ecdsa(self, data: bytes, signature: bytes, key: EncryptionKey) -> bool:
        """Vérification ECDSA."""
        public_key = serialization.load_pem_public_key(
            key.key_data,
            backend=self._backend
        )
        
        try:
            public_key.verify(
                signature,
                data,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception:
            return False
    
    async def _sign_ed25519(self, data: bytes, key: EncryptionKey) -> bytes:
        """Signature Ed25519."""
        signing_key = nacl.signing.SigningKey(key.key_data)
        signature = signing_key.sign(data)
        return signature.signature
    
    async def _verify_ed25519(self, data: bytes, signature: bytes, key: EncryptionKey) -> bool:
        """Vérification Ed25519."""
        verify_key = nacl.signing.VerifyKey(key.key_data)
        try:
            verify_key.verify(data, signature)
            return True
        except nacl.exceptions.BadSignatureError:
            return False
    
    # ========== MÉTHODES PRIVÉES - GESTION DES CLÉS ==========
    
    async def _get_key(self, key_id: Optional[str] = None) -> Optional[EncryptionKey]:
        """Récupère une clé avec cache."""
        key_id = key_id or self.config["default_key_id"]
        
        if not key_id:
            return None
        
        # Cache
        if self.config["enable_caching"]:
            with self._key_cache_lock:
                if key_id in self._key_cache:
                    key = self._key_cache[key_id]
                    if key.active and (not key.expires_at or datetime.now(timezone.utc) < key.expires_at):
                        self._stats["key_cache_hits"] += 1
                        return key
                    else:
                        del self._key_cache[key_id]
        
        self._stats["key_cache_misses"] += 1
        
        # Récupération depuis le gestionnaire de clés
        if self.key_manager:
            key = await self.key_manager.get_key(key_id)
            
            if key and self.config["enable_caching"]:
                with self._key_cache_lock:
                    if len(self._key_cache) < self.config["max_cache_size"]:
                        self._key_cache[key_id] = key
            
            return key
        
        return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        return self._stats
    
    def clear_cache(self) -> None:
        """Vide le cache des clés."""
        with self._key_cache_lock:
            self._key_cache.clear()


class KeyManagementService(KeyManagementInterface):
    """
    Service de gestion des clés avancé.
    Gère le cycle de vie des clés, la rotation, la dérivation et la distribution.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Cache des clés
        self._keys: Dict[str, EncryptionKey] = {}
        self._keys_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "keys_generated": 0,
            "keys_rotated": 0,
            "keys_deleted": 0,
            "key_retrievals": 0,
            "errors": 0
        }
        
        # Backend
        self._backend = default_backend()
        
        # Load initial des clés
        self._loaded = False
        
        logger.info("KeyManagementService initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "default_algorithm": EncryptionAlgorithm.AES_256_GCM,
            "default_class": DataClass.CONFIDENTIAL,
            "default_scope": EncryptionScope.BOTH,
            "key_rotation_days": 90,
            "key_expiration_days": 365,
            "derivation": {
                "algorithm": KeyDerivation.ARGON2,
                "iterations": 100000,
                "memory": 19 * 1024,
                "parallelism": 1,
                "salt_size": 32
            },
            "auto_rotate": True,
            "min_key_strength": 256,
            "backup_keys": True,
            "store_keys_encrypted": True
        }
    
    async def start(self) -> None:
        """Démarre le service de gestion des clés."""
        logger.info("KeyManagementService starting...")
        
        # Chargement des clés
        await self._load_keys()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._auto_rotation_loop())
        asyncio.create_task(self._backup_loop())
        
        logger.info("KeyManagementService started")
    
    async def stop(self) -> None:
        """Arrête le service de gestion des clés."""
        logger.info("KeyManagementService stopping...")
        # Sauvegarde des clés
        await self._save_keys()
        logger.info("KeyManagementService stopped")
    
    async def generate_key(
        self,
        algorithm: Optional[EncryptionAlgorithm] = None,
        key_class: Optional[DataClass] = None,
        scope: Optional[EncryptionScope] = None
    ) -> EncryptionKey:
        """Génère une nouvelle clé."""
        algorithm = algorithm or self.config["default_algorithm"]
        key_class = key_class or self.config["default_class"]
        scope = scope or self.config["default_scope"]
        
        self._stats["keys_generated"] += 1
        
        try:
            # Génération selon l'algorithme
            if algorithm in [EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.AES_256_CBC, EncryptionAlgorithm.AES_256_CTR]:
                key_data = os.urandom(32)
            
            elif algorithm in [EncryptionAlgorithm.CHACHA20_POLY1305]:
                key_data = os.urandom(32)
            
            elif algorithm in [EncryptionAlgorithm.RSA_2048]:
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                    backend=self._backend
                )
                key_data = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                key_material = {
                    "public_key": private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    ).decode()
                }
            
            elif algorithm in [EncryptionAlgorithm.RSA_4096]:
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=4096,
                    backend=self._backend
                )
                key_data = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                key_material = {
                    "public_key": private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    ).decode()
                }
            
            elif algorithm in [EncryptionAlgorithm.ECDSA_P256]:
                private_key = ec.generate_private_key(
                    ec.SECP256R1(),
                    backend=self._backend
                )
                key_data = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                key_material = {
                    "public_key": private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    ).decode()
                }
            
            elif algorithm in [EncryptionAlgorithm.ECDSA_P384]:
                private_key = ec.generate_private_key(
                    ec.SECP384R1(),
                    backend=self._backend
                )
                key_data = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                key_material = {
                    "public_key": private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    ).decode()
                }
            
            elif algorithm in [EncryptionAlgorithm.X25519]:
                private_key = nacl.signing.SigningKey.generate()
                key_data = private_key.encode()
                key_material = {
                    "public_key": base64.b64encode(private_key.verify_key.encode()).decode()
                }
            
            else:
                # Fallback AES-256
                key_data = os.urandom(32)
            
            # Création de la clé
            key = EncryptionKey(
                key_type=algorithm,
                key_data=key_data,
                key_material=key_material if 'key_material' in locals() else None,
                scope=scope,
                data_class=key_class,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=self.config["key_expiration_days"]),
                active=True,
                description=f"Auto-generated {algorithm.value} key"
            )
            
            # Stockage de la clé
            with self._keys_lock:
                self._keys[key.key_id] = key
            
            # Sauvegarde
            await self._save_key(key)
            
            logger.info(f"Key generated: {key.key_id} ({algorithm.value})")
            return key
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Key generation error: {e}")
            raise
    
    async def rotate_key(self, key_id: str) -> EncryptionKey:
        """Rote une clé."""
        self._stats["keys_rotated"] += 1
        
        with self._keys_lock:
            old_key = self._keys.get(key_id)
            if not old_key:
                raise ValueError(f"Key {key_id} not found")
            
            # Désactivation de l'ancienne clé
            old_key.active = False
            
            # Génération d'une nouvelle clé
            new_key = await self.generate_key(
                algorithm=old_key.key_type,
                key_class=old_key.data_class,
                scope=old_key.scope
            )
            
            # Métadonnées de rotation
            new_key.metadata["rotated_from"] = old_key.key_id
            new_key.metadata["rotation_timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # Stockage
            self._keys[new_key.key_id] = new_key
            
            logger.info(f"Key rotated: {key_id} -> {new_key.key_id}")
            return new_key
    
    async def get_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Récupère une clé."""
        self._stats["key_retrievals"] += 1
        
        with self._keys_lock:
            key = self._keys.get(key_id)
            
            # Vérification de la validité
            if key and key.active:
                if key.expires_at and datetime.now(timezone.utc) > key.expires_at:
                    key.active = False
                    return None
                return key
            
            return None
    
    async def delete_key(self, key_id: str) -> bool:
        """Supprime une clé."""
        self._stats["keys_deleted"] += 1
        
        with self._keys_lock:
            if key_id not in self._keys:
                return False
            
            del self._keys[key_id]
            
        # Suppression du storage
        await self._delete_key_from_storage(key_id)
        
        logger.info(f"Key deleted: {key_id}")
        return True
    
    async def list_keys(self) -> List[EncryptionKey]:
        """Liste toutes les clés."""
        with self._keys_lock:
            return list(self._keys.values())
    
    async def get_active_keys(self) -> List[EncryptionKey]:
        """Liste les clés actives."""
        with self._keys_lock:
            return [k for k in self._keys.values() if k.active]
    
    async def get_healthy_keys(self) -> List[EncryptionKey]:
        """Liste les clés actives et non expirées."""
        now = datetime.now(timezone.utc)
        with self._keys_lock:
            return [
                k for k in self._keys.values()
                if k.active and (not k.expires_at or k.expires_at > now)
            ]
    
    # ========== MÉTHODES PRIVÉES - STOCKAGE ==========
    
    async def _load_keys(self) -> None:
        """Charge les clés depuis le stockage."""
        if self._loaded:
            return
        
        try:
            if self.data_manager:
                # Récupération de toutes les clés
                keys_data = await self.data_manager.retrieve(
                    "keys:all",
                    DataType.CONFIG
                )
                
                if keys_data:
                    # Désérialisation
                    for key_dict in keys_data:
                        key = self._deserialize_key(key_dict)
                        if key:
                            with self._keys_lock:
                                self._keys[key.key_id] = key
            
            self._loaded = True
            logger.info(f"Loaded {len(self._keys)} keys")
            
        except Exception as e:
            logger.error(f"Error loading keys: {e}")
    
    async def _save_keys(self) -> None:
        """Sauvegarde toutes les clés."""
        try:
            with self._keys_lock:
                keys_data = [self._serialize_key(k) for k in self._keys.values()]
            
            if self.data_manager:
                await self.data_manager.store(
                    "keys:all",
                    keys_data,
                    DataType.CONFIG
                )
                
        except Exception as e:
            logger.error(f"Error saving keys: {e}")
    
    async def _save_key(self, key: EncryptionKey) -> None:
        """Sauvegarde une clé individuelle."""
        try:
            if self.data_manager:
                key_data = self._serialize_key(key)
                await self.data_manager.store(
                    f"key:{key.key_id}",
                    key_data,
                    DataType.CONFIG
                )
                
        except Exception as e:
            logger.error(f"Error saving key {key.key_id}: {e}")
    
    async def _delete_key_from_storage(self, key_id: str) -> None:
        """Supprime une clé du stockage."""
        try:
            if self.data_manager:
                await self.data_manager.delete(
                    f"key:{key_id}",
                    DataType.CONFIG
                )
                
        except Exception as e:
            logger.error(f"Error deleting key {key_id}: {e}")
    
    def _serialize_key(self, key: EncryptionKey) -> Dict:
        """Sérialise une clé."""
        return key.to_dict()
    
    def _deserialize_key(self, data: Dict) -> Optional[EncryptionKey]:
        """Désérialise une clé."""
        try:
            key = EncryptionKey(
                key_id=data.get("key_id", str(uuid.uuid4())),
                key_type=EncryptionAlgorithm(data.get("key_type", "aes-256-gcm")),
                key_data=base64.b64decode(data.get("key_data", b"")),
                key_material=data.get("key_material"),
                version=data.get("version", 1),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                expires_at=datetime.fromisoformat(data.get("expires_at")) if data.get("expires_at") else None,
                active=data.get("active", True),
                scope=EncryptionScope(data.get("scope", "both")),
                data_class=DataClass(data.get("data_class", "confidential")),
                owner=data.get("owner", ""),
                description=data.get("description", ""),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", [])
            )
            return key
        except Exception as e:
            logger.error(f"Error deserializing key: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - AUTOMATION ==========
    
    async def _auto_rotation_loop(self) -> None:
        """Boucle de rotation automatique des clés."""
        if not self.config["auto_rotate"]:
            return
        
        while True:
            await asyncio.sleep(86400)  # Une fois par jour
            
            try:
                with self._keys_lock:
                    now = datetime.now(timezone.utc)
                    for key_id, key in list(self._keys.items()):
                        if not key.active:
                            continue
                        
                        age = (now - key.created_at).days
                        if age >= self.config["key_rotation_days"]:
                            # Rotation automatique
                            try:
                                await self.rotate_key(key_id)
                                logger.info(f"Auto-rotated key: {key_id}")
                            except Exception as e:
                                logger.error(f"Auto-rotation failed for {key_id}: {e}")
                            
            except Exception as e:
                logger.error(f"Error in auto-rotation loop: {e}")
    
    async def _backup_loop(self) -> None:
        """Boucle de sauvegarde des clés."""
        while True:
            await asyncio.sleep(3600)  # Une fois par heure
            
            if self.config["backup_keys"]:
                try:
                    await self._save_keys()
                    logger.debug("Keys backed up")
                except Exception as e:
                    logger.error(f"Error backing up keys: {e}")


# ============== SECURITY CONTEXT ==============

class SecurityContext:
    """
    Contexte de sécurité pour les opérations de chiffrement.
    Gère l'authentification, l'autorisation et le contrôle d'accès.
    """
    
    def __init__(
        self,
        user_id: str,
        roles: List[str],
        permissions: List[str],
        data_class: DataClass = DataClass.CONFIDENTIAL
    ):
        self.user_id = user_id
        self.roles = roles
        self.permissions = permissions
        self.data_class = data_class
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now(timezone.utc)
        self.expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
        self.audit_logs: List[AuditLog] = []
    
    def has_permission(self, required_permission: str) -> bool:
        """Vérifie si l'utilisateur a une permission."""
        return required_permission in self.permissions
    
    def has_role(self, required_role: str) -> bool:
        """Vérifie si l'utilisateur a un rôle."""
        return required_role in self.roles
    
    def can_access(self, data_class: DataClass) -> bool:
        """Vérifie si l'utilisateur peut accéder à une classification."""
        # Top Secret peut accéder à tout
        if DataClass.TOP_SECRET in self.roles:
            return True
        
        # Sinon, vérification hiérarchique
        class_order = {
            DataClass.PUBLIC: 0,
            DataClass.INTERNAL: 1,
            DataClass.CONFIDENTIAL: 2,
            DataClass.SECRET: 3,
            DataClass.TOP_SECRET: 4,
            DataClass.RESTRICTED: 5
        }
        
        user_level = class_order.get(self.data_class, 0)
        required_level = class_order.get(data_class, 0)
        
        return user_level >= required_level
    
    def log_audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Dict[str, Any],
        success: bool = True
    ) -> None:
        """Log une action d'audit."""
        audit = AuditLog(
            action=action,
            user=self.user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            data_class=self.data_class,
            details=details,
            success=success,
            session_id=self.session_id
        )
        self.audit_logs.append(audit)
    
    def is_valid(self) -> bool:
        """Vérifie si le contexte est valide."""
        return datetime.now(timezone.utc) < self.expires_at
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "roles": self.roles,
            "permissions": self.permissions,
            "data_class": self.data_class.value,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat()
        }


# ============== FACTORY ==============

class EncryptionFactory:
    """Factory pour créer des composants de sécurité."""
    
    @staticmethod
    async def create_engine(
        key_manager: Optional[KeyManagementService] = None,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> EncryptionEngine:
        """Crée un moteur de chiffrement."""
        return EncryptionEngine(
            key_manager=key_manager,
            data_manager=data_manager,
            config=config
        )
    
    @staticmethod
    async def create_key_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> KeyManagementService:
        """Crée un service de gestion des clés."""
        service = KeyManagementService(
            data_manager=data_manager,
            config=config
        )
        await service.start()
        return service
    
    @staticmethod
    def create_security_context(
        user_id: str,
        roles: List[str],
        permissions: List[str],
        data_class: DataClass = DataClass.CONFIDENTIAL
    ) -> SecurityContext:
        """Crée un contexte de sécurité."""
        return SecurityContext(
            user_id=user_id,
            roles=roles,
            permissions=permissions,
            data_class=data_class
        )


# ============== EXPORT ==============

__all__ = [
    "EncryptionAlgorithm",
    "KeyDerivation",
    "DataClass",
    "EncryptionScope",
    "EncryptionKey",
    "EncryptedData",
    "SecurityPolicy",
    "AuditLog",
    "EncryptionEngine",
    "KeyManagementService",
    "SecurityContext",
    "EncryptionFactory"
]
