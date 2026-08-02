# trading/bots/hedge_bot/hedge_bot_encryptor.py

import asyncio
import logging
import time
import json
import hashlib
import base64
import os
import secrets
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


class EncryptionAlgorithm(str, Enum):
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


class KeyDerivation(str, Enum):
    PBKDF2 = "pbkdf2"
    SCRYPT = "scrypt"
    HKDF = "hkdf"
    ARGON2 = "argon2"
    BCrypt = "bcrypt"


class EncryptionMode(str, Enum):
    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"
    HYBRID = "hybrid"


@dataclass
class EncryptedData:
    id: str
    algorithm: EncryptionAlgorithm
    mode: EncryptionMode
    ciphertext: bytes
    iv: bytes
    salt: Optional[bytes] = None
    tag: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class EncryptionKey:
    id: str
    name: str
    algorithm: EncryptionAlgorithm
    mode: EncryptionMode
    key: Optional[bytes] = None
    public_key: Optional[bytes] = None
    private_key: Optional[bytes] = None
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EncryptedFile:
    id: str
    path: str
    encrypted_path: str
    algorithm: EncryptionAlgorithm
    size: int
    encrypted_size: int
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataEncryptor:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._keys: Dict[str, EncryptionKey] = {}
        self._encrypted_data: Dict[str, EncryptedData] = {}
        self._encrypted_files: Dict[str, EncryptedFile] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_keys()

    def _initialize_default_keys(self) -> None:
        master_key = self.generate_key(
            name="master",
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            mode=EncryptionMode.SYMMETRIC
        )
        self._keys["master"] = master_key

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    def generate_key(
        self,
        name: str,
        algorithm: EncryptionAlgorithm,
        mode: EncryptionMode = EncryptionMode.SYMMETRIC,
        key_size: int = 32,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EncryptionKey:
        key_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
        
        key = EncryptionKey(
            id=key_id,
            name=name,
            algorithm=algorithm,
            mode=mode,
            created_at=time.time(),
            expires_at=time.time() + expires_in if expires_in else None,
            metadata=metadata or {}
        )
        
        if mode == EncryptionMode.SYMMETRIC:
            key.key = secrets.token_bytes(key_size)
        
        elif mode == EncryptionMode.ASYMMETRIC:
            if algorithm in [EncryptionAlgorithm.RSA_OAEP, EncryptionAlgorithm.RSA_PKCS1]:
                if CRYPTOGRAPHY_AVAILABLE:
                    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                    key.private_key = private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                    key.public_key = private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
            elif algorithm == EncryptionAlgorithm.ECDH:
                if CRYPTOGRAPHY_AVAILABLE:
                    private_key = ec.generate_private_key(ec.SECP256R1())
                    key.private_key = private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                    key.public_key = private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
            elif algorithm == EncryptionAlgorithm.X25519:
                if CRYPTOGRAPHY_AVAILABLE:
                    private_key = ec.generate_private_key(ec.SECP256R1())
                    key.private_key = private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                    key.public_key = private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
        
        self._keys[key_id] = key
        return key

    def derive_key(
        self,
        password: str,
        salt: Optional[bytes] = None,
        key_size: int = 32,
        kdf: KeyDerivation = KeyDerivation.PBKDF2,
        iterations: int = 100000
    ) -> Tuple[bytes, bytes]:
        if salt is None:
            salt = secrets.token_bytes(16)
        
        if kdf == KeyDerivation.PBKDF2:
            kdf_obj = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=key_size,
                salt=salt,
                iterations=iterations,
                backend=default_backend()
            )
            key = kdf_obj.derive(password.encode())
        
        elif kdf == KeyDerivation.SCRYPT:
            kdf_obj = Scrypt(
                salt=salt,
                length=key_size,
                n=2**14,
                r=8,
                p=1,
                backend=default_backend()
            )
            key = kdf_obj.derive(password.encode())
        
        elif kdf == KeyDerivation.HKDF:
            kdf_obj = HKDF(
                algorithm=hashes.SHA256(),
                length=key_size,
                salt=salt,
                info=b'encryption_key',
                backend=default_backend()
            )
            key = kdf_obj.derive(password.encode())
        
        else:
            raise ValueError(f"Unsupported KDF: {kdf}")
        
        return key, salt

    async def encrypt(
        self,
        data: Union[str, bytes, Dict, List],
        key_id: str = "master",
        algorithm: Optional[EncryptionAlgorithm] = None,
        aad: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[EncryptedData]:
        async with self._lock:
            if key_id not in self._keys:
                return None
            
            key = self._keys[key_id]
            algorithm = algorithm or key.algorithm
            
            if isinstance(data, str):
                data = data.encode()
            elif isinstance(data, (dict, list)):
                data = json.dumps(data, default=str).encode()
            elif not isinstance(data, bytes):
                data = str(data).encode()
            
            iv = secrets.token_bytes(16)
            
            if algorithm in [EncryptionAlgorithm.AES_128_CBC, EncryptionAlgorithm.AES_192_CBC, EncryptionAlgorithm.AES_256_CBC]:
                ciphertext = self._encrypt_aes_cbc(data, key.key, iv, algorithm)
                tag = None
            elif algorithm in [EncryptionAlgorithm.AES_128_GCM, EncryptionAlgorithm.AES_192_GCM, EncryptionAlgorithm.AES_256_GCM]:
                ciphertext, tag = self._encrypt_aes_gcm(data, key.key, iv, algorithm, aad)
            elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                ciphertext, tag = self._encrypt_chacha20_poly1305(data, key.key, iv, aad)
            elif algorithm in [EncryptionAlgorithm.RSA_OAEP, EncryptionAlgorithm.RSA_PKCS1]:
                ciphertext = self._encrypt_rsa(data, key.public_key, algorithm)
                iv = b""
                tag = None
            else:
                return None
            
            encrypted_data = EncryptedData(
                id=hashlib.md5(f"{key_id}_{time.time()}".encode()).hexdigest(),
                algorithm=algorithm,
                mode=key.mode,
                ciphertext=ciphertext,
                iv=iv,
                tag=tag,
                metadata=metadata or {}
            )
            
            self._encrypted_data[encrypted_data.id] = encrypted_data
            await self._notify_observers("data_encrypted", encrypted_data)
            return encrypted_data

    def _encrypt_aes_cbc(self, data: bytes, key: bytes, iv: bytes, algorithm: EncryptionAlgorithm) -> bytes:
        if algorithm == EncryptionAlgorithm.AES_128_CBC:
            key = key[:16]
        elif algorithm == EncryptionAlgorithm.AES_192_CBC:
            key = key[:24]
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            key = key[:32]
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        pad_len = 16 - (len(data) % 16)
        padded_data = data + bytes([pad_len] * pad_len)
        
        return encryptor.update(padded_data) + encryptor.finalize()

    def _encrypt_aes_gcm(self, data: bytes, key: bytes, iv: bytes, algorithm: EncryptionAlgorithm, aad: Optional[bytes]) -> Tuple[bytes, bytes]:
        if algorithm == EncryptionAlgorithm.AES_128_GCM:
            key = key[:16]
        elif algorithm == EncryptionAlgorithm.AES_192_GCM:
            key = key[:24]
        elif algorithm == EncryptionAlgorithm.AES_256_GCM:
            key = key[:32]
        
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        if aad:
            encryptor.authenticate_additional_data(aad)
        
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return ciphertext, encryptor.tag

    def _encrypt_chacha20_poly1305(self, data: bytes, key: bytes, iv: bytes, aad: Optional[bytes]) -> Tuple[bytes, bytes]:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        
        chacha = ChaCha20Poly1305(key[:32])
        ciphertext = chacha.encrypt(iv[:12], data, aad or b"")
        return ciphertext[:-16], ciphertext[-16:]

    def _encrypt_rsa(self, data: bytes, public_key: bytes, algorithm: EncryptionAlgorithm) -> bytes:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography not available")
        
        pub_key = serialization.load_pem_public_key(public_key)
        
        if algorithm == EncryptionAlgorithm.RSA_OAEP:
            return pub_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        else:
            return pub_key.encrypt(
                data,
                padding.PKCS1v15()
            )

    async def decrypt(
        self,
        encrypted_id: str,
        key_id: str = "master",
        aad: Optional[bytes] = None
    ) -> Optional[bytes]:
        async with self._lock:
            if encrypted_id not in self._encrypted_data:
                return None
            
            if key_id not in self._keys:
                return None
            
            encrypted_data = self._encrypted_data[encrypted_id]
            key = self._keys[key_id]
            
            if encrypted_data.algorithm in [EncryptionAlgorithm.AES_128_CBC, EncryptionAlgorithm.AES_192_CBC, EncryptionAlgorithm.AES_256_CBC]:
                return self._decrypt_aes_cbc(encrypted_data.ciphertext, key.key, encrypted_data.iv, encrypted_data.algorithm)
            elif encrypted_data.algorithm in [EncryptionAlgorithm.AES_128_GCM, EncryptionAlgorithm.AES_192_GCM, EncryptionAlgorithm.AES_256_GCM]:
                return self._decrypt_aes_gcm(encrypted_data.ciphertext, key.key, encrypted_data.iv, encrypted_data.algorithm, encrypted_data.tag, aad)
            elif encrypted_data.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                return self._decrypt_chacha20_poly1305(encrypted_data.ciphertext, key.key, encrypted_data.iv, encrypted_data.tag, aad)
            elif encrypted_data.algorithm in [EncryptionAlgorithm.RSA_OAEP, EncryptionAlgorithm.RSA_PKCS1]:
                return self._decrypt_rsa(encrypted_data.ciphertext, key.private_key, encrypted_data.algorithm)
            else:
                return None

    def _decrypt_aes_cbc(self, ciphertext: bytes, key: bytes, iv: bytes, algorithm: EncryptionAlgorithm) -> bytes:
        if algorithm == EncryptionAlgorithm.AES_128_CBC:
            key = key[:16]
        elif algorithm == EncryptionAlgorithm.AES_192_CBC:
            key = key[:24]
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            key = key[:32]
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        pad_len = decrypted[-1]
        return decrypted[:-pad_len]

    def _decrypt_aes_gcm(self, ciphertext: bytes, key: bytes, iv: bytes, algorithm: EncryptionAlgorithm, tag: bytes, aad: Optional[bytes]) -> bytes:
        if algorithm == EncryptionAlgorithm.AES_128_GCM:
            key = key[:16]
        elif algorithm == EncryptionAlgorithm.AES_192_GCM:
            key = key[:24]
        elif algorithm == EncryptionAlgorithm.AES_256_GCM:
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

    def _decrypt_rsa(self, ciphertext: bytes, private_key: bytes, algorithm: EncryptionAlgorithm) -> bytes:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography not available")
        
        priv_key = serialization.load_pem_private_key(private_key, password=None)
        
        if algorithm == EncryptionAlgorithm.RSA_OAEP:
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

    async def encrypt_file(
        self,
        file_path: str,
        key_id: str = "master",
        output_path: Optional[str] = None,
        algorithm: Optional[EncryptionAlgorithm] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[EncryptedFile]:
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        encrypted_data = await self.encrypt(data, key_id, algorithm, metadata=metadata)
        
        if not encrypted_data:
            return None
        
        if output_path is None:
            output_path = f"{file_path}.encrypted"
        
        with open(output_path, 'wb') as f:
            f.write(encrypted_data.ciphertext)
        
        encrypted_file = EncryptedFile(
            id=hashlib.md5(f"{file_path}_{time.time()}".encode()).hexdigest(),
            path=file_path,
            encrypted_path=output_path,
            algorithm=encrypted_data.algorithm,
            size=os.path.getsize(file_path),
            encrypted_size=os.path.getsize(output_path),
            created_at=time.time(),
            metadata=metadata or {}
        )
        
        self._encrypted_files[encrypted_file.id] = encrypted_file
        await self._notify_observers("file_encrypted", encrypted_file)
        return encrypted_file

    async def decrypt_file(
        self,
        encrypted_file_id: str,
        key_id: str = "master",
        output_path: Optional[str] = None,
        aad: Optional[bytes] = None
    ) -> Optional[str]:
        if encrypted_file_id not in self._encrypted_files:
            return None
        
        encrypted_file = self._encrypted_files[encrypted_file_id]
        
        with open(encrypted_file.encrypted_path, 'rb') as f:
            ciphertext = f.read()
        
        encrypted_data = EncryptedData(
            id=encrypted_file_id,
            algorithm=encrypted_file.algorithm,
            mode=EncryptionMode.SYMMETRIC,
            ciphertext=ciphertext,
            iv=b"",
            metadata=encrypted_file.metadata
        )
        
        self._encrypted_data[encrypted_file_id] = encrypted_data
        
        decrypted_data = await self.decrypt(encrypted_file_id, key_id, aad)
        
        if decrypted_data is None:
            return None
        
        if output_path is None:
            output_path = encrypted_file.path
        
        with open(output_path, 'wb') as f:
            f.write(decrypted_data)
        
        return output_path

    async def get_key(self, key_id: str) -> Optional[EncryptionKey]:
        return self._keys.get(key_id)

    async def get_keys(self) -> List[EncryptionKey]:
        return list(self._keys.values())

    async def get_encrypted_data(self, encrypted_id: str) -> Optional[EncryptedData]:
        return self._encrypted_data.get(encrypted_id)

    async def get_encrypted_file(self, encrypted_file_id: str) -> Optional[EncryptedFile]:
        return self._encrypted_files.get(encrypted_file_id)

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
            "encrypted_data": len(self._encrypted_data),
            "encrypted_files": len(self._encrypted_files),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "EncryptionAlgorithm",
    "KeyDerivation",
    "EncryptionMode",
    "EncryptedData",
    "EncryptionKey",
    "EncryptedFile",
    "DataEncryptor"
]
