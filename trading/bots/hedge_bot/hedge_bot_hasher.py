# trading/bots/hedge_bot/hedge_bot_hasher.py

import asyncio
import logging
import time
import hashlib
import base64
import hmac
import secrets
import struct
import json
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import os

logger = logging.getLogger(__name__)


class HashAlgorithm(str, Enum):
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    SHA3_224 = "sha3_224"
    SHA3_256 = "sha3_256"
    SHA3_384 = "sha3_384"
    SHA3_512 = "sha3_512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"
    SM3 = "sm3"
    RIPEMD160 = "ripemd160"
    WHIRLPOOL = "whirlpool"


class HashEncoding(str, Enum):
    HEX = "hex"
    BASE64 = "base64"
    BASE64URL = "base64url"
    BINARY = "binary"


class HashPurpose(str, Enum):
    DATA_INTEGRITY = "data_integrity"
    PASSWORD = "password"
    AUTHENTICATION = "authentication"
    DEDUPLICATION = "deduplication"
    CACHING = "caching"
    SIGNATURE = "signature"
    FINGERPRINT = "fingerprint"
    IDENTIFIER = "identifier"
    VERIFICATION = "verification"


@dataclass
class HashResult:
    id: str
    algorithm: HashAlgorithm
    encoding: HashEncoding
    purpose: HashPurpose
    hash_value: str
    input_length: int
    timestamp: float
    digest: bytes
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HashConfig:
    id: str
    name: str
    algorithm: HashAlgorithm
    encoding: HashEncoding = HashEncoding.HEX
    salt: Optional[bytes] = None
    iterations: int = 1
    key: Optional[bytes] = None
    purpose: HashPurpose = HashPurpose.DATA_INTEGRITY
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HashVerification:
    id: str
    hash_id: str
    verified: bool
    input_length: int
    timestamp: float
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataHasher:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._configs: Dict[str, HashConfig] = {}
        self._results: Dict[str, HashResult] = {}
        self._verifications: Dict[str, HashVerification] = {}
        self._cache: Dict[str, HashResult] = {}
        self._cache_ttl = 3600
        self._salt_cache: Dict[str, bytes] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_configs()

    def _initialize_default_configs(self) -> None:
        default_configs = [
            HashConfig(
                id="default",
                name="Default SHA256",
                algorithm=HashAlgorithm.SHA256,
                purpose=HashPurpose.DATA_INTEGRITY
            ),
            HashConfig(
                id="password",
                name="Password Hashing",
                algorithm=HashAlgorithm.SHA256,
                encoding=HashEncoding.BASE64,
                iterations=10000,
                purpose=HashPurpose.PASSWORD
            ),
            HashConfig(
                id="signature",
                name="Signature Hashing",
                algorithm=HashAlgorithm.SHA512,
                purpose=HashPurpose.SIGNATURE
            ),
            HashConfig(
                id="fingerprint",
                name="Fingerprint Hashing",
                algorithm=HashAlgorithm.SHA384,
                purpose=HashPurpose.FINGERPRINT
            ),
            HashConfig(
                id="deduplication",
                name="Deduplication Hashing",
                algorithm=HashAlgorithm.BLAKE2B,
                purpose=HashPurpose.DEDUPLICATION
            )
        ]
        
        for config in default_configs:
            self._configs[config.id] = config

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_config(
        self,
        name: str,
        algorithm: HashAlgorithm,
        encoding: HashEncoding = HashEncoding.HEX,
        iterations: int = 1,
        purpose: HashPurpose = HashPurpose.DATA_INTEGRITY,
        salt: Optional[bytes] = None,
        key: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> HashConfig:
        async with self._lock:
            config_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            config = HashConfig(
                id=config_id,
                name=name,
                algorithm=algorithm,
                encoding=encoding,
                iterations=iterations,
                purpose=purpose,
                salt=salt,
                key=key,
                metadata=metadata or {}
            )
            
            self._configs[config_id] = config
            await self._notify_observers("config_created", config)
            return config

    async def hash_data(
        self,
        data: Union[str, bytes, Dict, List],
        config_id: str = "default",
        use_cache: bool = True
    ) -> Optional[HashResult]:
        async with self._lock:
            if config_id not in self._configs:
                return None
            
            config = self._configs[config_id]
            
            data_bytes = self._serialize_data(data)
            
            cache_key = f"{config_id}_{hashlib.md5(data_bytes).hexdigest()}_{config.iterations}"
            
            if use_cache and cache_key in self._cache:
                cached = self._cache[cache_key]
                if time.time() - cached.timestamp < self._cache_ttl:
                    return cached
            
            result = await self._compute_hash(data_bytes, config)
            
            if result:
                self._results[result.id] = result
                
                if use_cache:
                    self._cache[cache_key] = result
                
                await self._notify_observers("hash_computed", result)
            
            return result

    async def _compute_hash(self, data: bytes, config: HashConfig) -> HashResult:
        result_id = hashlib.md5(f"{config.algorithm.value}_{time.time()}_{len(data)}".encode()).hexdigest()
        
        digest = data
        
        for i in range(config.iterations):
            if config.salt:
                digest = self._apply_salt(digest, config.salt, i)
            
            digest = self._apply_hash(digest, config.algorithm)
            
            if config.key:
                digest = self._apply_hmac(digest, config.key)
        
        hash_value = self._encode_digest(digest, config.encoding)
        
        return HashResult(
            id=result_id,
            algorithm=config.algorithm,
            encoding=config.encoding,
            purpose=config.purpose,
            hash_value=hash_value,
            input_length=len(data),
            timestamp=time.time(),
            digest=digest,
            metadata=config.metadata
        )

    def _apply_hash(self, data: bytes, algorithm: HashAlgorithm) -> bytes:
        if algorithm == HashAlgorithm.MD5:
            return hashlib.md5(data).digest()
        elif algorithm == HashAlgorithm.SHA1:
            return hashlib.sha1(data).digest()
        elif algorithm == HashAlgorithm.SHA256:
            return hashlib.sha256(data).digest()
        elif algorithm == HashAlgorithm.SHA384:
            return hashlib.sha384(data).digest()
        elif algorithm == HashAlgorithm.SHA512:
            return hashlib.sha512(data).digest()
        elif algorithm == HashAlgorithm.SHA3_224:
            return hashlib.sha3_224(data).digest()
        elif algorithm == HashAlgorithm.SHA3_256:
            return hashlib.sha3_256(data).digest()
        elif algorithm == HashAlgorithm.SHA3_384:
            return hashlib.sha3_384(data).digest()
        elif algorithm == HashAlgorithm.SHA3_512:
            return hashlib.sha3_512(data).digest()
        elif algorithm == HashAlgorithm.BLAKE2B:
            return hashlib.blake2b(data).digest()
        elif algorithm == HashAlgorithm.BLAKE2S:
            return hashlib.blake2s(data).digest()
        elif algorithm == HashAlgorithm.SM3:
            return hashlib.sm3(data).digest()
        elif algorithm == HashAlgorithm.RIPEMD160:
            try:
                from Crypto.Hash import RIPEMD160
                return RIPEMD160.new(data).digest()
            except ImportError:
                logger.warning("RIPEMD160 not available, falling back to SHA256")
                return hashlib.sha256(data).digest()
        elif algorithm == HashAlgorithm.WHIRLPOOL:
            try:
                from Crypto.Hash import Whirlpool
                return Whirlpool.new(data).digest()
            except ImportError:
                logger.warning("Whirlpool not available, falling back to SHA512")
                return hashlib.sha512(data).digest()
        else:
            return hashlib.sha256(data).digest()

    def _apply_salt(self, data: bytes, salt: bytes, iteration: int) -> bytes:
        salt_data = salt + struct.pack('>I', iteration)
        return data + salt_data

    def _apply_hmac(self, data: bytes, key: bytes) -> bytes:
        return hmac.new(key, data, hashlib.sha256).digest()

    def _encode_digest(self, digest: bytes, encoding: HashEncoding) -> str:
        if encoding == HashEncoding.HEX:
            return digest.hex()
        elif encoding == HashEncoding.BASE64:
            return base64.b64encode(digest).decode()
        elif encoding == HashEncoding.BASE64URL:
            return base64.urlsafe_b64encode(digest).decode()
        elif encoding == HashEncoding.BINARY:
            return digest.hex()
        else:
            return digest.hex()

    def _decode_digest(self, hash_value: str, encoding: HashEncoding) -> bytes:
        if encoding == HashEncoding.HEX:
            return bytes.fromhex(hash_value)
        elif encoding == HashEncoding.BASE64:
            return base64.b64decode(hash_value)
        elif encoding == HashEncoding.BASE64URL:
            return base64.urlsafe_b64decode(hash_value)
        elif encoding == HashEncoding.BINARY:
            return bytes.fromhex(hash_value)
        else:
            return bytes.fromhex(hash_value)

    def _serialize_data(self, data: Any) -> bytes:
        if isinstance(data, str):
            return data.encode('utf-8')
        elif isinstance(data, bytes):
            return data
        elif isinstance(data, (dict, list)):
            return json.dumps(data, default=str).encode('utf-8')
        elif isinstance(data, (int, float, bool)):
            return str(data).encode('utf-8')
        elif isinstance(data, Decimal):
            return str(data).encode('utf-8')
        elif isinstance(data, datetime):
            return data.isoformat().encode('utf-8')
        else:
            try:
                return pickle.dumps(data)
            except:
                return str(data).encode('utf-8')

    async def verify_hash(
        self,
        data: Union[str, bytes, Dict, List],
        hash_value: str,
        config_id: str = "default"
    ) -> Optional[HashVerification]:
        async with self._lock:
            if config_id not in self._configs:
                return None
            
            config = self._configs[config_id]
            
            result = await self.hash_data(data, config_id, use_cache=False)
            
            if not result:
                return None
            
            verified = result.hash_value == hash_value
            
            verification = HashVerification(
                id=hashlib.md5(f"{result.id}_{time.time()}".encode()).hexdigest(),
                hash_id=result.id,
                verified=verified,
                input_length=len(self._serialize_data(data)),
                timestamp=time.time(),
                reason=None if verified else "Hash mismatch"
            )
            
            self._verifications[verification.id] = verification
            await self._notify_observers("hash_verified", verification)
            
            return verification

    async def generate_salt(self, length: int = 32) -> bytes:
        return secrets.token_bytes(length)

    async def generate_key(self, length: int = 32) -> bytes:
        return secrets.token_bytes(length)

    async def compute_merkle_root(self, data_list: List[Any], config_id: str = "default") -> Optional[str]:
        if not data_list:
            return None
        
        hashes = []
        for data in data_list:
            result = await self.hash_data(data, config_id)
            if result:
                hashes.append(result.hash_value)
        
        if not hashes:
            return None
        
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])
            
            next_level = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i+1]
                result = await self.hash_data(combined, config_id)
                if result:
                    next_level.append(result.hash_value)
            
            hashes = next_level
        
        return hashes[0] if hashes else None

    async def compute_merkle_proof(
        self,
        data: Any,
        data_list: List[Any],
        config_id: str = "default"
    ) -> Optional[Tuple[List[str], str]]:
        if not data_list:
            return None
        
        data_hash = await self.hash_data(data, config_id)
        if not data_hash:
            return None
        
        hashes = []
        for item in data_list:
            result = await self.hash_data(item, config_id)
            if result:
                hashes.append(result.hash_value)
        
        if not hashes:
            return None
        
        target_hash = data_hash.hash_value
        target_index = -1
        
        for i, h in enumerate(hashes):
            if h == target_hash:
                target_index = i
                break
        
        if target_index == -1:
            return None
        
        proof = []
        current_hashes = hashes.copy()
        idx = target_index
        
        while len(current_hashes) > 1:
            if len(current_hashes) % 2 != 0:
                current_hashes.append(current_hashes[-1])
            
            next_level = []
            for i in range(0, len(current_hashes), 2):
                combined = current_hashes[i] + current_hashes[i+1]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            
            if idx % 2 == 0:
                if idx + 1 < len(current_hashes):
                    proof.append(current_hashes[idx + 1])
            else:
                proof.append(current_hashes[idx - 1])
            
            idx = idx // 2
            current_hashes = next_level
        
        root_hash = current_hashes[0] if current_hashes else ""
        
        return proof, root_hash

    async def verify_merkle_proof(
        self,
        data: Any,
        proof: List[str],
        root_hash: str,
        config_id: str = "default"
    ) -> bool:
        data_hash = await self.hash_data(data, config_id)
        if not data_hash:
            return False
        
        current = data_hash.hash_value
        
        for sibling in proof:
            if current < sibling:
                combined = current + sibling
            else:
                combined = sibling + current
            
            result = await self.hash_data(combined, config_id)
            if not result:
                return False
            
            current = result.hash_value
        
        return current == root_hash

    async def get_config(self, config_id: str) -> Optional[HashConfig]:
        return self._configs.get(config_id)

    async def get_configs(self) -> List[HashConfig]:
        return list(self._configs.values())

    async def get_result(self, result_id: str) -> Optional[HashResult]:
        return self._results.get(result_id)

    async def get_results(self, limit: int = 100) -> List[HashResult]:
        return list(self._results.values())[-limit:]

    async def get_verification(self, verification_id: str) -> Optional[HashVerification]:
        return self._verifications.get(verification_id)

    async def clear_cache(self) -> None:
        self._cache.clear()

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
            "configs": len(self._configs),
            "results": len(self._results),
            "verifications": len(self._verifications),
            "cache_size": len(self._cache),
            "cache_ttl": self._cache_ttl,
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "HashAlgorithm",
    "HashEncoding",
    "HashPurpose",
    "HashResult",
    "HashConfig",
    "HashVerification",
    "DataHasher"
]
