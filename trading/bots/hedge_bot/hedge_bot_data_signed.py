# trading/bots/hedge_bot/hedge_bot_data_signed.py

import asyncio
import logging
import time
import json
import hashlib
import base64
import hmac
import struct
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
    from cryptography.hazmat.backends import default_backend
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


class SignatureAlgorithm(str, Enum):
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA384 = "hmac_sha384"
    HMAC_SHA512 = "hmac_sha512"
    RSA_SHA256 = "rsa_sha256"
    RSA_SHA384 = "rsa_sha384"
    RSA_SHA512 = "rsa_sha512"
    ECDSA_SHA256 = "ecdsa_sha256"
    ECDSA_SHA384 = "ecdsa_sha384"
    ECDSA_SHA512 = "ecdsa_sha512"
    ED25519 = "ed25519"
    JWT = "jwt"
    NONE = "none"


class SignaturePurpose(str, Enum):
    AUTHENTICATION = "authentication"
    INTEGRITY = "integrity"
    NON_REPUDIATION = "non_repudiation"
    AUTHORIZATION = "authorization"
    VERIFICATION = "verification"
    DATA_VALIDATION = "data_validation"
    MESSAGE_VALIDATION = "message_validation"
    CERTIFICATE = "certificate"
    TIMESTAMP = "timestamp"
    CONSENT = "consent"


class SignatureStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class SignatureKey:
    id: str
    name: str
    algorithm: SignatureAlgorithm
    purpose: SignaturePurpose
    public_key: Optional[bytes] = None
    private_key: Optional[bytes] = None
    secret_key: Optional[bytes] = None
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    revoked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Signature:
    id: str
    key_id: str
    algorithm: SignatureAlgorithm
    purpose: SignaturePurpose
    data_hash: str
    signature: bytes
    timestamp: float
    expires_at: Optional[float] = None
    status: SignatureStatus = SignatureStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignatureVerification:
    id: str
    signature_id: str
    status: SignatureStatus
    message: str
    timestamp: float
    verified_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignedData:
    id: str
    data: bytes
    signature_id: str
    signature: bytes
    algorithm: SignatureAlgorithm
    timestamp: float
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataSigner:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._keys: Dict[str, SignatureKey] = {}
        self._signatures: Dict[str, Signature] = {}
        self._verifications: Dict[str, SignatureVerification] = {}
        self._signed_data: Dict[str, SignedData] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_keys()

    def _initialize_default_keys(self) -> None:
        default_keys = [
            SignatureKey(
                id="default_hmac",
                name="Default HMAC Key",
                algorithm=SignatureAlgorithm.HMAC_SHA256,
                purpose=SignaturePurpose.AUTHENTICATION,
                secret_key=base64.b64encode(hashlib.sha256(b"default_secret").digest())
            ),
            SignatureKey(
                id="default_jwt",
                name="Default JWT Key",
                algorithm=SignatureAlgorithm.JWT,
                purpose=SignaturePurpose.AUTHENTICATION,
                secret_key=base64.b64encode(hashlib.sha256(b"jwt_secret").digest())
            )
        ]
        
        for key in default_keys:
            self._keys[key.id] = key

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_key(
        self,
        name: str,
        algorithm: SignatureAlgorithm,
        purpose: SignaturePurpose = SignaturePurpose.AUTHENTICATION,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SignatureKey:
        async with self._lock:
            key_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            key = SignatureKey(
                id=key_id,
                name=name,
                algorithm=algorithm,
                purpose=purpose,
                created_at=time.time(),
                expires_at=time.time() + expires_in if expires_in else None,
                metadata=metadata or {}
            )
            
            if algorithm in [SignatureAlgorithm.HMAC_SHA256, SignatureAlgorithm.HMAC_SHA384, SignatureAlgorithm.HMAC_SHA512]:
                key.secret_key = await self._generate_hmac_key(algorithm)
            elif algorithm in [SignatureAlgorithm.RSA_SHA256, SignatureAlgorithm.RSA_SHA384, SignatureAlgorithm.RSA_SHA512]:
                pub_key, priv_key = await self._generate_rsa_key(algorithm)
                key.public_key = pub_key
                key.private_key = priv_key
            elif algorithm in [SignatureAlgorithm.ECDSA_SHA256, SignatureAlgorithm.ECDSA_SHA384, SignatureAlgorithm.ECDSA_SHA512]:
                pub_key, priv_key = await self._generate_ec_key(algorithm)
                key.public_key = pub_key
                key.private_key = priv_key
            elif algorithm == SignatureAlgorithm.ED25519:
                pub_key, priv_key = await self._generate_ed25519_key()
                key.public_key = pub_key
                key.private_key = priv_key
            elif algorithm == SignatureAlgorithm.JWT:
                key.secret_key = await self._generate_jwt_key()
            
            self._keys[key_id] = key
            await self._notify_observers("key_created", key)
            return key

    async def _generate_hmac_key(self, algorithm: SignatureAlgorithm) -> bytes:
        if algorithm == SignatureAlgorithm.HMAC_SHA256:
            return base64.b64encode(hashlib.sha256(os.urandom(32)).digest())
        elif algorithm == SignatureAlgorithm.HMAC_SHA384:
            return base64.b64encode(hashlib.sha384(os.urandom(48)).digest())
        elif algorithm == SignatureAlgorithm.HMAC_SHA512:
            return base64.b64encode(hashlib.sha512(os.urandom(64)).digest())
        return base64.b64encode(os.urandom(32))

    async def _generate_rsa_key(self, algorithm: SignatureAlgorithm) -> Tuple[bytes, bytes]:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography not available")
        
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return public_bytes, private_bytes

    async def _generate_ec_key(self, algorithm: SignatureAlgorithm) -> Tuple[bytes, bytes]:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography not available")
        
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return public_bytes, private_bytes

    async def _generate_ed25519_key(self) -> Tuple[bytes, bytes]:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography not available")
        
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        return public_bytes, private_bytes

    async def _generate_jwt_key(self) -> bytes:
        return base64.b64encode(os.urandom(32))

    async def sign(
        self,
        data: Union[str, bytes, Dict, List],
        key_id: str = "default_hmac",
        purpose: SignaturePurpose = SignaturePurpose.AUTHENTICATION,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Signature]:
        async with self._lock:
            if key_id not in self._keys:
                return None
            
            key = self._keys[key_id]
            
            data_bytes = self._serialize_data(data)
            data_hash = hashlib.sha256(data_bytes).hexdigest()
            
            signature_bytes = await self._compute_signature(data_bytes, key)
            
            if not signature_bytes:
                return None
            
            sig = Signature(
                id=hashlib.md5(f"{key_id}_{time.time()}".encode()).hexdigest(),
                key_id=key_id,
                algorithm=key.algorithm,
                purpose=purpose,
                data_hash=data_hash,
                signature=signature_bytes,
                timestamp=time.time(),
                expires_at=time.time() + expires_in if expires_in else None,
                status=SignatureStatus.VERIFIED,
                metadata=metadata or {}
            )
            
            self._signatures[sig.id] = sig
            await self._notify_observers("signature_created", sig)
            return sig

    async def _compute_signature(self, data: bytes, key: SignatureKey) -> Optional[bytes]:
        if key.algorithm == SignatureAlgorithm.HMAC_SHA256:
            return hmac.new(key.secret_key, data, hashlib.sha256).digest()
        elif key.algorithm == SignatureAlgorithm.HMAC_SHA384:
            return hmac.new(key.secret_key, data, hashlib.sha384).digest()
        elif key.algorithm == SignatureAlgorithm.HMAC_SHA512:
            return hmac.new(key.secret_key, data, hashlib.sha512).digest()
        elif key.algorithm in [SignatureAlgorithm.RSA_SHA256, SignatureAlgorithm.RSA_SHA384, SignatureAlgorithm.RSA_SHA512]:
            if not CRYPTOGRAPHY_AVAILABLE:
                return None
            private_key = serialization.load_pem_private_key(key.private_key, password=None)
            hash_alg = self._get_hash_algorithm(key.algorithm)
            return private_key.sign(data, padding.PKCS1v15(), hash_alg)
        elif key.algorithm in [SignatureAlgorithm.ECDSA_SHA256, SignatureAlgorithm.ECDSA_SHA384, SignatureAlgorithm.ECDSA_SHA512]:
            if not CRYPTOGRAPHY_AVAILABLE:
                return None
            private_key = serialization.load_pem_private_key(key.private_key, password=None)
            hash_alg = self._get_hash_algorithm(key.algorithm)
            return private_key.sign(data, ec.ECDSA(hash_alg))
        elif key.algorithm == SignatureAlgorithm.ED25519:
            if not CRYPTOGRAPHY_AVAILABLE:
                return None
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(key.private_key)
            return private_key.sign(data)
        elif key.algorithm == SignatureAlgorithm.JWT:
            if not JOSE_AVAILABLE:
                return None
            payload = {"data": data.decode('utf-8', errors='ignore')}
            return jwt.encode(payload, key.secret_key, algorithm='HS256').encode()
        else:
            return None

    async def verify(
        self,
        data: Union[str, bytes, Dict, List],
        signature: bytes,
        key_id: str = "default_hmac",
        algorithm: Optional[SignatureAlgorithm] = None
    ) -> SignatureVerification:
        async with self._lock:
            if key_id not in self._keys:
                return self._create_verification("", SignatureStatus.FAILED, "Key not found")
            
            key = self._keys[key_id]
            algorithm = algorithm or key.algorithm
            
            data_bytes = self._serialize_data(data)
            data_hash = hashlib.sha256(data_bytes).hexdigest()
            
            is_valid = await self._verify_signature(data_bytes, signature, key, algorithm)
            
            status = SignatureStatus.VERIFIED if is_valid else SignatureStatus.INVALID
            
            verification = SignatureVerification(
                id=hashlib.md5(f"{key_id}_{time.time()}".encode()).hexdigest(),
                signature_id="",
                status=status,
                message="Signature verified" if is_valid else "Signature verification failed",
                timestamp=time.time()
            )
            
            self._verifications[verification.id] = verification
            await self._notify_observers("verification_completed", verification)
            return verification

    async def _verify_signature(
        self,
        data: bytes,
        signature: bytes,
        key: SignatureKey,
        algorithm: SignatureAlgorithm
    ) -> bool:
        try:
            if algorithm == SignatureAlgorithm.HMAC_SHA256:
                expected = hmac.new(key.secret_key, data, hashlib.sha256).digest()
                return hmac.compare_digest(signature, expected)
            elif algorithm == SignatureAlgorithm.HMAC_SHA384:
                expected = hmac.new(key.secret_key, data, hashlib.sha384).digest()
                return hmac.compare_digest(signature, expected)
            elif algorithm == SignatureAlgorithm.HMAC_SHA512:
                expected = hmac.new(key.secret_key, data, hashlib.sha512).digest()
                return hmac.compare_digest(signature, expected)
            elif algorithm in [SignatureAlgorithm.RSA_SHA256, SignatureAlgorithm.RSA_SHA384, SignatureAlgorithm.RSA_SHA512]:
                if not CRYPTOGRAPHY_AVAILABLE:
                    return False
                public_key = serialization.load_pem_public_key(key.public_key)
                hash_alg = self._get_hash_algorithm(algorithm)
                try:
                    public_key.verify(signature, data, padding.PKCS1v15(), hash_alg)
                    return True
                except:
                    return False
            elif algorithm in [SignatureAlgorithm.ECDSA_SHA256, SignatureAlgorithm.ECDSA_SHA384, SignatureAlgorithm.ECDSA_SHA512]:
                if not CRYPTOGRAPHY_AVAILABLE:
                    return False
                public_key = serialization.load_pem_public_key(key.public_key)
                hash_alg = self._get_hash_algorithm(algorithm)
                try:
                    public_key.verify(signature, data, ec.ECDSA(hash_alg))
                    return True
                except:
                    return False
            elif algorithm == SignatureAlgorithm.ED25519:
                if not CRYPTOGRAPHY_AVAILABLE:
                    return False
                public_key = ed25519.Ed25519PublicKey.from_public_bytes(key.public_key)
                try:
                    public_key.verify(signature, data)
                    return True
                except:
                    return False
            elif algorithm == SignatureAlgorithm.JWT:
                if not JOSE_AVAILABLE:
                    return False
                try:
                    jwt.decode(signature.decode(), key.secret_key, algorithms=['HS256'])
                    return True
                except:
                    return False
            else:
                return False
        except Exception:
            return False

    def _get_hash_algorithm(self, algorithm: SignatureAlgorithm) -> Any:
        if algorithm in [SignatureAlgorithm.RSA_SHA256, SignatureAlgorithm.ECDSA_SHA256]:
            return hashes.SHA256()
        elif algorithm in [SignatureAlgorithm.RSA_SHA384, SignatureAlgorithm.ECDSA_SHA384]:
            return hashes.SHA384()
        elif algorithm in [SignatureAlgorithm.RSA_SHA512, SignatureAlgorithm.ECDSA_SHA512]:
            return hashes.SHA512()
        return hashes.SHA256()

    def _serialize_data(self, data: Any) -> bytes:
        if isinstance(data, str):
            return data.encode('utf-8')
        elif isinstance(data, bytes):
            return data
        elif isinstance(data, (dict, list)):
            return json.dumps(data, default=str).encode('utf-8')
        elif isinstance(data, (int, float, bool)):
            return str(data).encode('utf-8')
        else:
            try:
                return pickle.dumps(data)
            except:
                return str(data).encode('utf-8')

    def _create_verification(self, signature_id: str, status: SignatureStatus, message: str) -> SignatureVerification:
        return SignatureVerification(
            id=hashlib.md5(f"{signature_id}_{time.time()}".encode()).hexdigest(),
            signature_id=signature_id,
            status=status,
            message=message,
            timestamp=time.time()
        )

    async def create_signed_data(
        self,
        data: Union[str, bytes, Dict, List],
        key_id: str = "default_hmac",
        purpose: SignaturePurpose = SignaturePurpose.INTEGRITY,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SignedData]:
        signature = await self.sign(data, key_id, purpose, expires_in, metadata)
        if not signature:
            return None
        
        data_bytes = self._serialize_data(data)
        
        signed = SignedData(
            id=hashlib.md5(f"{signature.id}_{time.time()}".encode()).hexdigest(),
            data=data_bytes,
            signature_id=signature.id,
            signature=signature.signature,
            algorithm=signature.algorithm,
            timestamp=time.time(),
            expires_at=signature.expires_at,
            metadata=metadata or {}
        )
        
        self._signed_data[signed.id] = signed
        await self._notify_observers("signed_data_created", signed)
        return signed

    async def verify_signed_data(self, signed_data_id: str) -> Optional[SignatureVerification]:
        if signed_data_id not in self._signed_data:
            return None
        
        signed = self._signed_data[signed_data_id]
        signature = self._signatures.get(signed.signature_id)
        
        if not signature:
            return self._create_verification("", SignatureStatus.FAILED, "Signature not found")
        
        return await self.verify(signed.data, signed.signature, signature.key_id, signed.algorithm)

    async def get_key(self, key_id: str) -> Optional[SignatureKey]:
        return self._keys.get(key_id)

    async def get_keys(self) -> List[SignatureKey]:
        return list(self._keys.values())

    async def get_signature(self, signature_id: str) -> Optional[Signature]:
        return self._signatures.get(signature_id)

    async def get_verification(self, verification_id: str) -> Optional[SignatureVerification]:
        return self._verifications.get(verification_id)

    async def get_signed_data(self, signed_data_id: str) -> Optional[SignedData]:
        return self._signed_data.get(signed_data_id)

    async def revoke_key(self, key_id: str) -> bool:
        if key_id in self._keys:
            self._keys[key_id].revoked = True
            await self._notify_observers("key_revoked", key_id)
            return True
        return False

    async def delete_key(self, key_id: str) -> bool:
        if key_id in self._keys:
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
            "signatures": len(self._signatures),
            "verifications": len(self._verifications),
            "signed_data": len(self._signed_data),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "SignatureAlgorithm",
    "SignaturePurpose",
    "SignatureStatus",
    "SignatureKey",
    "Signature",
    "SignatureVerification",
    "SignedData",
    "DataSigner"
]
