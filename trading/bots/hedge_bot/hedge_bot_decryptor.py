# trading/bots/hedge_bot/hedge_bot_decryptor.py

import asyncio
import logging
import time
import json
import hashlib
import base64
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, ec, ed25519, padding
    from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.backends import default_backend
    from cryptography.x509 import Certificate, load_pem_x509_certificate
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

try:
    from jose import jwt, jwk
    from jose.constants import ALGORITHMS
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False

logger = logging.getLogger(__name__)


class DecryptionAlgorithm(str, Enum):
    AES_128_CBC = "aes_128_cbc"
    AES_192_CBC = "aes_192_cbc"
    AES_256_CBC = "aes_256_cbc"
    AES_128_GCM = "aes_128_gcm"
    AES_192_GCM = "aes_192_gcm"
    AES_256_GCM = "aes_256_gcm"
    CHACHA20_POLY1305 = "chacha20_poly1305"
    RSA_OAEP = "rsa_oaep"
    RSA_PKCS1 = "rsa_pkcs1"
    ECDH = "ecdh"
    X25519 = "x25519"


class DecryptionMode(str, Enum):
    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"
    HYBRID = "hybrid"


class DecryptionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    PENDING = "pending"
    REJECTED = "rejected"


@dataclass
class DecryptionKey:
    id: str
    name: str
    algorithm: DecryptionAlgorithm
    mode: DecryptionMode
    key: Optional[bytes] = None
    public_key: Optional[bytes] = None
    private_key: Optional[bytes] = None
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecryptedData:
    id: str
    algorithm: DecryptionAlgorithm
    mode: DecryptionMode
    plaintext: bytes
    metadata: Dict[str, Any] = field(default_factory=dict)
    decrypted_at: float = field(default_factory=time.time)
    status: DecryptionStatus = DecryptionStatus.SUCCESS


@dataclass
class DecryptionRequest:
    id: str
    data: bytes
    algorithm: DecryptionAlgorithm
    mode: DecryptionMode
    key_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    status: DecryptionStatus = DecryptionStatus.PENDING
    result: Optional[DecryptedData] = None


@dataclass
class DecryptionSession:
    id: str
    key_id: str
    algorithm: DecryptionAlgorithm
    mode: DecryptionMode
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataDecryptor:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._keys: Dict[str, DecryptionKey] = {}
        self._decrypted_data: Dict[str, DecryptedData] = {}
        self._requests: Dict[str, DecryptionRequest] = {}
        self._sessions: Dict[str, DecryptionSession] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_keys()

    def _initialize_default_keys(self) -> None:
        master_key = DecryptionKey(
            id="master",
            name="Master Decryption Key",
            algorithm=DecryptionAlgorithm.AES_256_GCM,
            mode=DecryptionMode.SYMMETRIC,
            key=base64.b64encode(os.urandom(32))
        )
        self._keys["master"] = master_key

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    def add_key(
        self,
        name: str,
        algorithm: DecryptionAlgorithm,
        mode: DecryptionMode,
        key: Optional[bytes] = None,
        public_key: Optional[bytes] = None,
        private_key: Optional[bytes] = None,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DecryptionKey:
        key_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
        
        decryption_key = DecryptionKey(
            id=key_id,
            name=name,
            algorithm=algorithm,
            mode=mode,
            key=key,
            public_key=public_key,
            private_key=private_key,
            created_at=time.time(),
            expires_at=time.time() + expires_in if expires_in else None,
            metadata=metadata or {}
        )
        
        self._keys[key_id] = decryption_key
        return decryption_key

    async def decrypt(
        self,
        ciphertext: bytes,
        key_id: str = "master",
        algorithm: Optional[DecryptionAlgorithm] = None,
        iv: Optional[bytes] = None,
        tag: Optional[bytes] = None,
        aad: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DecryptedData]:
        async with self._lock:
            if key_id not in self._keys:
                return None
            
            key = self._keys[key_id]
            algorithm = algorithm or key.algorithm
            
            request = DecryptionRequest(
                id=hashlib.md5(f"{key_id}_{time.time()}".encode()).hexdigest(),
                data=ciphertext,
                algorithm=algorithm,
                mode=key.mode,
                key_id=key_id,
                metadata=metadata or {}
            )
            
            self._requests[request.id] = request
            
            try:
                if key.mode == DecryptionMode.SYMMETRIC:
                    plaintext = await self._decrypt_symmetric(ciphertext, key, algorithm, iv, tag, aad)
                elif key.mode == DecryptionMode.ASYMMETRIC:
                    plaintext = await self._decrypt_asymmetric(ciphertext, key, algorithm)
                else:
                    return None
                
                decrypted = DecryptedData(
                    id=hashlib.md5(f"{request.id}_{time.time()}".encode()).hexdigest(),
                    algorithm=algorithm,
                    mode=key.mode,
                    plaintext=plaintext,
                    metadata=metadata or {},
                    status=DecryptionStatus.SUCCESS
                )
                
                self._decrypted_data[decrypted.id] = decrypted
                request.status = DecryptionStatus.SUCCESS
                request.result = decrypted
                
                await self._notify_observers("decryption_completed", decrypted)
                return decrypted
                
            except Exception as e:
                logger.error(f"Decryption error: {e}")
                request.status = DecryptionStatus.FAILED
                await self._notify_observers("decryption_failed", request, str(e))
                return None

    async def _decrypt_symmetric(
        self,
        ciphertext: bytes,
        key: DecryptionKey,
        algorithm: DecryptionAlgorithm,
        iv: Optional[bytes],
        tag: Optional[bytes],
        aad: Optional[bytes]
    ) -> bytes:
        if algorithm in [DecryptionAlgorithm.AES_128_CBC, DecryptionAlgorithm.AES_192_CBC, DecryptionAlgorithm.AES_256_CBC]:
            return self._decrypt_aes_cbc(ciphertext, key.key, iv, algorithm)
        elif algorithm in [DecryptionAlgorithm.AES_128_GCM, DecryptionAlgorithm.AES_192_GCM, DecryptionAlgorithm.AES_256_GCM]:
            return self._decrypt_aes_gcm(ciphertext, key.key, iv, algorithm, tag, aad)
        elif algorithm == DecryptionAlgorithm.CHACHA20_POLY1305:
            return self._decrypt_chacha20_poly1305(ciphertext, key.key, iv, tag, aad)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    def _decrypt_aes_cbc(self, ciphertext: bytes, key: bytes, iv: bytes, algorithm: DecryptionAlgorithm) -> bytes:
        if algorithm == DecryptionAlgorithm.AES_128_CBC:
            key = key[:16]
        elif algorithm == DecryptionAlgorithm.AES_192_CBC:
            key = key[:24]
        elif algorithm == DecryptionAlgorithm.AES_256_CBC:
            key = key[:32]
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        pad_len = decrypted[-1]
        return decrypted[:-pad_len]

    def _decrypt_aes_gcm(self, ciphertext: bytes, key: bytes, iv: bytes, algorithm: DecryptionAlgorithm, tag: bytes, aad: Optional[bytes]) -> bytes:
        if algorithm == DecryptionAlgorithm.AES_128_GCM:
            key = key[:16]
        elif algorithm == DecryptionAlgorithm.AES_192_GCM:
            key = key[:24]
        elif algorithm == DecryptionAlgorithm.AES_256_GCM:
            key = key[:32]
        
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        
        if aad:
            decryptor.authenticate_additional_data(aad)
        
        return decryptor.update(ciphertext) + decryptor.finalize()

    def _decrypt_chacha20_poly1305(self, ciphertext: bytes, key: bytes, iv: bytes, tag: bytes, aad: Optional[bytes]) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        
        chacha = ChaCha20Poly1305(key[:32])
        return chacha.decrypt(iv[:12], ciphertext + tag, aad or b"")

    async def _decrypt_asymmetric(
        self,
        ciphertext: bytes,
        key: DecryptionKey,
        algorithm: DecryptionAlgorithm
    ) -> bytes:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography not available")
        
        if algorithm in [DecryptionAlgorithm.RSA_OAEP, DecryptionAlgorithm.RSA_PKCS1]:
            return self._decrypt_rsa(ciphertext, key.private_key, algorithm)
        else:
            raise ValueError(f"Unsupported asymmetric algorithm: {algorithm}")

    def _decrypt_rsa(self, ciphertext: bytes, private_key: bytes, algorithm: DecryptionAlgorithm) -> bytes:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography not available")
        
        priv_key = serialization.load_pem_private_key(private_key, password=None)
        
        if algorithm == DecryptionAlgorithm.RSA_OAEP:
            return priv_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        else:
            return priv_key.decrypt(
                ciphertext,
                padding.PKCS1v15()
            )

    async def create_session(
        self,
        key_id: str,
        duration: int = 3600,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DecryptionSession]:
        if key_id not in self._keys:
            return None
        
        key = self._keys[key_id]
        
        session = DecryptionSession(
            id=hashlib.md5(f"{key_id}_{time.time()}".encode()).hexdigest(),
            key_id=key_id,
            algorithm=key.algorithm,
            mode=key.mode,
            expires_at=time.time() + duration,
            metadata=metadata or {}
        )
        
        self._sessions[session.id] = session
        return session

    async def decrypt_with_session(
        self,
        session_id: str,
        ciphertext: bytes,
        iv: Optional[bytes] = None,
        tag: Optional[bytes] = None,
        aad: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DecryptedData]:
        if session_id not in self._sessions:
            return None
        
        session = self._sessions[session_id]
        
        if session.expires_at and session.expires_at < time.time():
            session.status = "expired"
            return None
        
        return await self.decrypt(
            ciphertext,
            session.key_id,
            session.algorithm,
            iv,
            tag,
            aad,
            metadata
        )

    async def get_key(self, key_id: str) -> Optional[DecryptionKey]:
        return self._keys.get(key_id)

    async def get_keys(self) -> List[DecryptionKey]:
        return list(self._keys.values())

    async def get_decrypted_data(self, decrypted_id: str) -> Optional[DecryptedData]:
        return self._decrypted_data.get(decrypted_id)

    async def get_request(self, request_id: str) -> Optional[DecryptionRequest]:
        return self._requests.get(request_id)

    async def get_session(self, session_id: str) -> Optional[DecryptionSession]:
        return self._sessions.get(session_id)

    async def revoke_key(self, key_id: str) -> bool:
        if key_id in self._keys:
            self._keys[key_id].expires_at = time.time() - 1
            await self._notify_observers("key_revoked", key_id)
            return True
        return False

    async def delete_key(self, key_id: str) -> bool:
        if key_id in self._keys and key_id != "master":
            del self._keys[key_id]
            await self._notify_observers("key_deleted", key_id)
            return True
        return False

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "keys": len(self._keys),
            "decrypted_data": len(self._decrypted_data),
            "requests": len(self._requests),
            "sessions": len(self._sessions),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "DecryptionAlgorithm",
    "DecryptionMode",
    "DecryptionStatus",
    "DecryptionKey",
    "DecryptedData",
    "DecryptionRequest",
    "DecryptionSession",
    "DataDecryptor"
]
