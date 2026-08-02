# trading/bots/hedge_bot/hedge_bot_data_secure.py

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
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.backends import default_backend
    from cryptography.x509 import Certificate, load_pem_x509_certificate
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

try:
    from jose import jwt, jwk
    from jose.exceptions import JWTError
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(str, Enum):
    AES_128 = "aes-128"
    AES_192 = "aes-192"
    AES_256 = "aes-256"
    CHACHA20 = "chacha20"
    RSA = "rsa"
    ECDSA = "ecdsa"
    ED25519 = "ed25519"


class KeyDerivation(str, Enum):
    PBKDF2 = "pbkdf2"
    SCRYPT = "scrypt"
    ARGON2 = "argon2"
    BCrypt = "bcrypt"


class SecurityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAXIMUM = "maximum"


@dataclass
class SecureData:
    id: str
    data: bytes
    encrypted: bytes
    iv: bytes
    salt: bytes
    algorithm: EncryptionAlgorithm
    key_derivation: KeyDerivation
    created_at: float
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecureKey:
    id: str
    algorithm: EncryptionAlgorithm
    key: bytes
    public_key: Optional[bytes] = None
    private_key: Optional[bytes] = None
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecureToken:
    id: str
    token: str
    payload: Dict[str, Any]
    created_at: float
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecureCertificate:
    id: str
    subject: str
    issuer: str
    certificate: bytes
    private_key: bytes
    public_key: bytes
    serial_number: str
    not_before: float
    not_after: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataSecurityManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._keys: Dict[str, SecureKey] = {}
        self._secure_data: Dict[str, SecureData] = {}
        self._tokens: Dict[str, SecureToken] = {}
        self._certificates: Dict[str, SecureCertificate] = {}
        self._default_algorithm = EncryptionAlgorithm.AES_256
        self._default_kdf = KeyDerivation.PBKDF2
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_keys()

    def _initialize_default_keys(self) -> None:
        master_key = self.generate_key(EncryptionAlgorithm.AES_256)
        self._keys["master"] = master_key

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    def generate_key(
        self,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256,
        key_size: int = 32
    ) -> SecureKey:
        key_id = hashlib.md5(f"{algorithm.value}_{time.time()}".encode()).hexdigest()
        
        if algorithm in [EncryptionAlgorithm.AES_128, EncryptionAlgorithm.AES_192, EncryptionAlgorithm.AES_256, EncryptionAlgorithm.CHACHA20]:
            key = secrets.token_bytes(key_size)
            return SecureKey(id=key_id, algorithm=algorithm, key=key)
        
        elif algorithm == EncryptionAlgorithm.RSA:
            if CRYPTOGRAPHY_AVAILABLE:
                private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                private_bytes = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                public_bytes = private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                return SecureKey(
                    id=key_id,
                    algorithm=algorithm,
                    key=private_bytes,
                    public_key=public_bytes,
                    private_key=private_bytes
                )
        
        elif algorithm == EncryptionAlgorithm.ECDSA:
            if CRYPTOGRAPHY_AVAILABLE:
                private_key = ec.generate_private_key(ec.SECP256R1())
                private_bytes = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                public_bytes = private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                return SecureKey(
                    id=key_id,
                    algorithm=algorithm,
                    key=private_bytes,
                    public_key=public_bytes,
                    private_key=private_bytes
                )
        
        elif algorithm == EncryptionAlgorithm.ED25519:
            if CRYPTOGRAPHY_AVAILABLE:
                private_key = ed25519.Ed25519PrivateKey.generate()
                private_bytes = private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                )
                public_bytes = private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                )
                return SecureKey(
                    id=key_id,
                    algorithm=algorithm,
                    key=private_bytes,
                    public_key=public_bytes,
                    private_key=private_bytes
                )
        
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    def derive_key(
        self,
        password: str,
        salt: Optional[bytes] = None,
        key_size: int = 32,
        kdf: KeyDerivation = KeyDerivation.PBKDF2
    ) -> Tuple[bytes, bytes]:
        if salt is None:
            salt = secrets.token_bytes(16)
        
        if kdf == KeyDerivation.PBKDF2:
            kdf_obj = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=key_size,
                salt=salt,
                iterations=100000,
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
        
        else:
            raise ValueError(f"Unsupported KDF: {kdf}")
        
        return key, salt

    async def encrypt(
        self,
        data: Union[str, bytes],
        key_id: str = "master",
        algorithm: Optional[EncryptionAlgorithm] = None,
        iv: Optional[bytes] = None
    ) -> SecureData:
        async with self._lock:
            if key_id not in self._keys:
                raise ValueError(f"Key not found: {key_id}")
            
            key_obj = self._keys[key_id]
            algorithm = algorithm or key_obj.algorithm
            
            if isinstance(data, str):
                data = data.encode()
            
            if iv is None:
                iv = secrets.token_bytes(16)
            
            if algorithm in [EncryptionAlgorithm.AES_128, EncryptionAlgorithm.AES_192, EncryptionAlgorithm.AES_256]:
                encrypted, salt = self._encrypt_aes(data, key_obj.key, iv, algorithm)
            elif algorithm == EncryptionAlgorithm.CHACHA20:
                encrypted, salt = self._encrypt_chacha20(data, key_obj.key, iv)
            elif algorithm == EncryptionAlgorithm.RSA:
                encrypted, salt = self._encrypt_rsa(data, key_obj.public_key)
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            
            secure_data = SecureData(
                id=hashlib.md5(f"{key_id}_{time.time()}".encode()).hexdigest(),
                data=data,
                encrypted=encrypted,
                iv=iv,
                salt=salt or b"",
                algorithm=algorithm,
                key_derivation=KeyDerivation.PBKDF2,
                created_at=time.time()
            )
            
            self._secure_data[secure_data.id] = secure_data
            await self._notify_observers("data_encrypted", secure_data)
            return secure_data

    def _encrypt_aes(self, data: bytes, key: bytes, iv: bytes, algorithm: EncryptionAlgorithm) -> Tuple[bytes, bytes]:
        if algorithm == EncryptionAlgorithm.AES_128:
            key = key[:16]
        elif algorithm == EncryptionAlgorithm.AES_192:
            key = key[:24]
        elif algorithm == EncryptionAlgorithm.AES_256:
            key = key[:32]
        else:
            key = key[:32]
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        pad_len = 16 - (len(data) % 16)
        padded_data = data + bytes([pad_len] * pad_len)
        
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        return encrypted, b""

    def _encrypt_chacha20(self, data: bytes, key: bytes, iv: bytes) -> Tuple[bytes, bytes]:
        cipher = Cipher(algorithms.ChaCha20(key[:32], iv[:16]), mode=None, backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(data)
        return encrypted, b""

    def _encrypt_rsa(self, data: bytes, public_key: bytes) -> Tuple[bytes, bytes]:
        if CRYPTOGRAPHY_AVAILABLE:
            pub_key = serialization.load_pem_public_key(public_key)
            encrypted = pub_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return encrypted, b""
        raise RuntimeError("Cryptography not available")

    async def decrypt(self, secure_id: str) -> Optional[bytes]:
        async with self._lock:
            if secure_id not in self._secure_data:
                return None
            
            secure_data = self._secure_data[secure_id]
            
            if secure_data.algorithm in [EncryptionAlgorithm.AES_128, EncryptionAlgorithm.AES_192, EncryptionAlgorithm.AES_256]:
                decrypted = self._decrypt_aes(secure_data.encrypted, secure_data.iv, secure_data.algorithm)
            elif secure_data.algorithm == EncryptionAlgorithm.CHACHA20:
                decrypted = self._decrypt_chacha20(secure_data.encrypted, secure_data.iv)
            elif secure_data.algorithm == EncryptionAlgorithm.RSA:
                decrypted = self._decrypt_rsa(secure_data.encrypted)
            else:
                return None
            
            return decrypted

    def _decrypt_aes(self, encrypted: bytes, iv: bytes, algorithm: EncryptionAlgorithm) -> bytes:
        key = self._keys["master"].key
        if algorithm == EncryptionAlgorithm.AES_128:
            key = key[:16]
        elif algorithm == EncryptionAlgorithm.AES_192:
            key = key[:24]
        else:
            key = key[:32]
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted) + decryptor.finalize()
        
        pad_len = decrypted[-1]
        return decrypted[:-pad_len]

    def _decrypt_chacha20(self, encrypted: bytes, iv: bytes) -> bytes:
        key = self._keys["master"].key[:32]
        cipher = Cipher(algorithms.ChaCha20(key, iv[:16]), mode=None, backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted)

    def _decrypt_rsa(self, encrypted: bytes) -> bytes:
        if CRYPTOGRAPHY_AVAILABLE:
            key = self._keys["master"].key
            priv_key = serialization.load_pem_private_key(key, password=None)
            decrypted = priv_key.decrypt(
                encrypted,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return decrypted
        raise RuntimeError("Cryptography not available")

    async def generate_token(
        self,
        payload: Dict[str, Any],
        key_id: str = "master",
        expires_in: int = 3600,
        algorithm: str = "HS256"
    ) -> SecureToken:
        if not JOSE_AVAILABLE:
            raise RuntimeError("python-jose not available")
        
        token_id = hashlib.md5(f"{payload.get('sub', '')}_{time.time()}".encode()).hexdigest()
        
        created_at = time.time()
        expires_at = created_at + expires_in if expires_in > 0 else None
        
        token_payload = {
            "iat": created_at,
            "exp": expires_at,
            "jti": token_id,
            **payload
        }
        
        key = self._keys.get(key_id)
        if not key:
            raise ValueError(f"Key not found: {key_id}")
        
        token = jwt.encode(token_payload, key.key, algorithm=algorithm)
        
        secure_token = SecureToken(
            id=token_id,
            token=token,
            payload=token_payload,
            created_at=created_at,
            expires_at=expires_at
        )
        
        self._tokens[token_id] = secure_token
        await self._notify_observers("token_generated", secure_token)
        return secure_token

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not JOSE_AVAILABLE:
            raise RuntimeError("python-jose not available")
        
        for key in self._keys.values():
            try:
                payload = jwt.decode(token, key.key, algorithms=["HS256", "RS256", "ES256", "EdDSA"])
                return payload
            except JWTError:
                continue
        
        return None

    async def generate_certificate(
        self,
        subject: str,
        issuer: str,
        days_valid: int = 365,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.RSA
    ) -> SecureCertificate:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography not available")
        
        import datetime as dt
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        
        key_obj = self.generate_key(algorithm)
        
        subject_attrs = [
            x509.NameAttribute(NameOID.COMMON_NAME, subject)
        ]
        issuer_attrs = [
            x509.NameAttribute(NameOID.COMMON_NAME, issuer)
        ]
        
        not_before = dt.datetime.now()
        not_after = not_before + dt.timedelta(days=days_valid)
        
        private_key = serialization.load_pem_private_key(key_obj.private_key, password=None)
        
        certificate = x509.CertificateBuilder()\
            .subject_name(x509.Name(subject_attrs))\
            .issuer_name(x509.Name(issuer_attrs))\
            .public_key(private_key.public_key())\
            .serial_number(x509.random_serial_number())\
            .not_valid_before(not_before)\
            .not_valid_after(not_after)\
            .sign(private_key, hashes.SHA256())
        
        cert_bytes = certificate.public_bytes(serialization.Encoding.PEM)
        
        secure_cert = SecureCertificate(
            id=hashlib.md5(f"{subject}_{time.time()}".encode()).hexdigest(),
            subject=subject,
            issuer=issuer,
            certificate=cert_bytes,
            private_key=key_obj.private_key,
            public_key=key_obj.public_key,
            serial_number=str(certificate.serial_number),
            not_before=not_before.timestamp(),
            not_after=not_after.timestamp()
        )
        
        self._certificates[secure_cert.id] = secure_cert
        await self._notify_observers("certificate_generated", secure_cert)
        return secure_cert

    async def hash_password(
        self,
        password: str,
        salt: Optional[bytes] = None,
        iterations: int = 100000
    ) -> Tuple[str, str]:
        if salt is None:
            salt = os.urandom(16)
        
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt,
            iterations,
            dklen=32
        )
        
        salt_b64 = base64.b64encode(salt).decode()
        hash_b64 = base64.b64encode(key).decode()
        
        return hash_b64, salt_b64

    async def verify_password(self, password: str, hash_b64: str, salt_b64: str) -> bool:
        salt = base64.b64decode(salt_b64.encode())
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt,
            100000,
            dklen=32
        )
        new_hash = base64.b64encode(key).decode()
        return new_hash == hash_b64

    async def sanitize_data(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        result = data.copy()
        for field in fields:
            if field in result:
                result[field] = "[REDACTED]"
        return result

    async def anonymize_data(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        import hashlib
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = hashlib.sha256(str(result[field]).encode()).hexdigest()[:16]
        return result

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
            "secure_data": len(self._secure_data),
            "tokens": len(self._tokens),
            "certificates": len(self._certificates),
            "running": self._running
        }


__all__ = [
    "EncryptionAlgorithm",
    "KeyDerivation",
    "SecurityLevel",
    "SecureData",
    "SecureKey",
    "SecureToken",
    "SecureCertificate",
    "DataSecurityManager"
]
