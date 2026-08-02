# trading/bots/hedge_bot/hedge_bot_data_provenanced.py

import asyncio
import json
import logging
import time
import hashlib
import hmac
import base64
import uuid
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import zlib
import pickle

try:
    import cryptography
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa, ed25519
    from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15, OAEP, MGF1
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.x509 import Certificate, load_pem_x509_certificate
except ImportError:
    print("cryptography not installed. Please install: pip install cryptography")
    raise

try:
    import jwt
except ImportError:
    print("PyJWT not installed. Please install: pip install PyJWT")
    raise

logger = logging.getLogger(__name__)


class ProvenanceType(str, Enum):
    TRADE = "trade"
    ORDER = "order"
    SIGNAL = "signal"
    DECISION = "decision"
    POSITION = "position"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    PERFORMANCE = "performance"
    ALERT = "alert"
    CONFIG = "config"
    STATE = "state"
    BACKTEST = "backtest"
    VALIDATION = "validation"
    CORRECTION = "correction"
    AUDIT = "audit"
    COMPLIANCE = "compliance"


class IntegrityStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    FAILED = "failed"
    CORRUPTED = "corrupted"
    TAMPERED = "tampered"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class SignatureAlgorithm(str, Enum):
    ECDSA = "ecdsa"
    ED25519 = "ed25519"
    RSA = "rsa"
    HMAC = "hmac"
    JWT = "jwt"


@dataclass
class ProvenanceRecord:
    id: str
    type: ProvenanceType
    data: Any
    timestamp: float
    source: str
    hash: str
    signature: bytes
    signer: str
    algorithm: SignatureAlgorithm
    previous_hash: Optional[str] = None
    integrity_status: IntegrityStatus = IntegrityStatus.UNVERIFIED
    metadata: Dict[str, Any] = field(default_factory=dict)
    proof: Optional[bytes] = None
    verification_time: Optional[float] = None
    verified_by: Optional[str] = None


@dataclass
class ProvenanceChain:
    id: str
    name: str
    records: List[ProvenanceRecord]
    created_at: float
    updated_at: float
    last_hash: Optional[str] = None
    size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvenanceProof:
    record_id: str
    proof_type: str
    data: bytes
    timestamp: float
    verifier: str
    status: IntegrityStatus
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrustAnchor:
    id: str
    name: str
    public_key: bytes
    algorithm: SignatureAlgorithm
    created_at: float
    expires_at: Optional[float] = None
    revoked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class CryptographicUtils:
    
    @staticmethod
    def generate_key_pair(algorithm: SignatureAlgorithm = SignatureAlgorithm.ED25519) -> Tuple[bytes, bytes]:
        if algorithm == SignatureAlgorithm.ED25519:
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            return (
                private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                ),
                public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                )
            )
        elif algorithm == SignatureAlgorithm.ECDSA:
            private_key = ec.generate_private_key(ec.SECP256K1())
            public_key = private_key.public_key()
            return (
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ),
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
            )
        elif algorithm == SignatureAlgorithm.RSA:
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            public_key = private_key.public_key()
            return (
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ),
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
            )
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    @staticmethod
    def sign_data(data: bytes, private_key: bytes, algorithm: SignatureAlgorithm) -> bytes:
        if algorithm == SignatureAlgorithm.ED25519:
            key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
            return key.sign(data)
        elif algorithm == SignatureAlgorithm.ECDSA:
            key = serialization.load_pem_private_key(private_key, password=None)
            return key.sign(data, ec.ECDSA(hashes.SHA256()))
        elif algorithm == SignatureAlgorithm.RSA:
            key = serialization.load_pem_private_key(private_key, password=None)
            return key.sign(data, PKCS1v15(), hashes.SHA256())
        elif algorithm == SignatureAlgorithm.HMAC:
            return hmac.new(private_key, data, hashlib.sha256).digest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    @staticmethod
    def verify_signature(data: bytes, signature: bytes, public_key: bytes, algorithm: SignatureAlgorithm) -> bool:
        try:
            if algorithm == SignatureAlgorithm.ED25519:
                key = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
                key.verify(signature, data)
                return True
            elif algorithm == SignatureAlgorithm.ECDSA:
                key = serialization.load_pem_public_key(public_key)
                key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
                return True
            elif algorithm == SignatureAlgorithm.RSA:
                key = serialization.load_pem_public_key(public_key)
                key.verify(signature, data, PKCS1v15(), hashes.SHA256())
                return True
            elif algorithm == SignatureAlgorithm.HMAC:
                expected = hmac.new(public_key, data, hashlib.sha256).digest()
                return hmac.compare_digest(signature, expected)
            else:
                return False
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    @staticmethod
    def compute_hash(data: bytes, algorithm: str = "sha256") -> str:
        if algorithm == "sha256":
            return hashlib.sha256(data).hexdigest()
        elif algorithm == "sha512":
            return hashlib.sha512(data).hexdigest()
        elif algorithm == "md5":
            return hashlib.md5(data).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    @staticmethod
    def compute_merkle_root(hashes: List[str]) -> str:
        if not hashes:
            return ""
        
        current = hashes.copy()
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    combined = current[i] + current[i + 1]
                    next_level.append(hashlib.sha256(combined.encode()).hexdigest())
                else:
                    next_level.append(current[i])
            current = next_level
        
        return current[0] if current else ""

    @staticmethod
    def compute_merkle_proof(hashes: List[str], index: int) -> List[str]:
        if not hashes or index >= len(hashes):
            return []
        
        proof = []
        current = hashes.copy()
        idx = index
        
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    combined = current[i] + current[i + 1]
                    next_level.append(hashlib.sha256(combined.encode()).hexdigest())
                    if i == idx or i + 1 == idx:
                        proof.append(current[i + 1] if i == idx else current[i])
                else:
                    next_level.append(current[i])
            idx = idx // 2
            current = next_level
        
        return proof

    @staticmethod
    def verify_merkle_proof(proof: List[str], leaf_hash: str, root_hash: str) -> bool:
        current = leaf_hash
        for sibling in proof:
            combined = current + sibling if current < sibling else sibling + current
            current = hashlib.sha256(combined.encode()).hexdigest()
        return current == root_hash

    @staticmethod
    def encrypt_data(data: bytes, key: bytes) -> bytes:
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        pad_len = 16 - (len(data) % 16)
        padded_data = data + bytes([pad_len] * pad_len)
        
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        return iv + encrypted

    @staticmethod
    def decrypt_data(encrypted_data: bytes, key: bytes) -> bytes:
        iv = encrypted_data[:16]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted = decryptor.update(encrypted_data[16:]) + decryptor.finalize()
        pad_len = decrypted[-1]
        return decrypted[:-pad_len]

    @staticmethod
    def derive_key(password: str, salt: bytes, iterations: int = 100000) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        return kdf.derive(password.encode())


class ProvenanceChainManager:
    
    def __init__(self, name: str = "nexus_provenance"):
        self.name = name
        self._chains: Dict[str, ProvenanceChain] = {}
        self._trust_anchors: Dict[str, TrustAnchor] = {}
        self._records: Dict[str, ProvenanceRecord] = {}
        self._proofs: Dict[str, ProvenanceProof] = {}
        self._lock = asyncio.Lock()
        self._crypto = CryptographicUtils()
        self._default_algorithm = SignatureAlgorithm.ED25519
        self._signing_key: Optional[bytes] = None
        self._verification_key: Optional[bytes] = None
        self._storage_path: Optional[str] = None
        self._initialized = False
        
        self._initialize_trust_anchors()

    def _initialize_trust_anchors(self) -> None:
        private_key, public_key = self._crypto.generate_key_pair(SignatureAlgorithm.ED25519)
        
        self._signing_key = private_key
        self._verification_key = public_key
        
        anchor = TrustAnchor(
            id="nexus_root",
            name="NEXUS Root Trust Anchor",
            public_key=public_key,
            algorithm=SignatureAlgorithm.ED25519,
            created_at=time.time(),
            expires_at=time.time() + 31536000,
            revoked=False,
            metadata={"purpose": "root_verification"}
        )
        self._trust_anchors[anchor.id] = anchor
        self._initialized = True

    def set_storage_path(self, path: str) -> None:
        self._storage_path = path
        os.makedirs(path, exist_ok=True)

    async def create_chain(self, name: str, metadata: Dict[str, Any] = None) -> str:
        async with self._lock:
            chain_id = str(uuid.uuid4())
            chain = ProvenanceChain(
                id=chain_id,
                name=name,
                records=[],
                created_at=time.time(),
                updated_at=time.time(),
                metadata=metadata or {}
            )
            self._chains[chain_id] = chain
            return chain_id

    async def add_record(
        self,
        chain_id: str,
        record_type: ProvenanceType,
        data: Any,
        source: str,
        previous_hash: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        async with self._lock:
            if chain_id not in self._chains:
                logger.error(f"Chain {chain_id} not found")
                return None
            
            chain = self._chains[chain_id]
            record_id = str(uuid.uuid4())
            
            data_bytes = pickle.dumps(data)
            data_hash = self._crypto.compute_hash(data_bytes)
            
            if previous_hash is None:
                previous_hash = chain.last_hash
            
            record_data = {
                "id": record_id,
                "type": record_type.value,
                "data_hash": data_hash,
                "timestamp": time.time(),
                "source": source,
                "previous_hash": previous_hash,
                "metadata": metadata or {}
            }
            
            record_bytes = pickle.dumps(record_data)
            signature = self._crypto.sign_data(
                record_bytes,
                self._signing_key,
                self._default_algorithm
            )
            
            record = ProvenanceRecord(
                id=record_id,
                type=record_type,
                data=data,
                timestamp=time.time(),
                source=source,
                hash=data_hash,
                signature=signature,
                signer="nexus_root",
                algorithm=self._default_algorithm,
                previous_hash=previous_hash,
                metadata=metadata or {}
            )
            
            chain.records.append(record)
            chain.last_hash = data_hash
            chain.updated_at = time.time()
            chain.size += 1
            
            self._records[record_id] = record
            
            return record_id

    async def verify_record(self, record_id: str) -> IntegrityStatus:
        async with self._lock:
            if record_id not in self._records:
                return IntegrityStatus.UNVERIFIED
            
            record = self._records[record_id]
            
            data_bytes = pickle.dumps(record.data)
            computed_hash = self._crypto.compute_hash(data_bytes)
            
            if computed_hash != record.hash:
                record.integrity_status = IntegrityStatus.CORRUPTED
                return IntegrityStatus.CORRUPTED
            
            record_data = {
                "id": record.id,
                "type": record.type.value,
                "data_hash": record.hash,
                "timestamp": record.timestamp,
                "source": record.source,
                "previous_hash": record.previous_hash,
                "metadata": record.metadata
            }
            record_bytes = pickle.dumps(record_data)
            
            if record_id in self._trust_anchors:
                anchor = self._trust_anchors[record.signer]
                is_valid = self._crypto.verify_signature(
                    record_bytes,
                    record.signature,
                    anchor.public_key,
                    record.algorithm
                )
            else:
                is_valid = self._crypto.verify_signature(
                    record_bytes,
                    record.signature,
                    self._verification_key,
                    record.algorithm
                )
            
            if is_valid:
                record.integrity_status = IntegrityStatus.VERIFIED
                record.verification_time = time.time()
                return IntegrityStatus.VERIFIED
            else:
                record.integrity_status = IntegrityStatus.TAMPERED
                return IntegrityStatus.TAMPERED

    async def verify_chain(self, chain_id: str) -> Dict[str, IntegrityStatus]:
        async with self._lock:
            if chain_id not in self._chains:
                return {}
            
            chain = self._chains[chain_id]
            results = {}
            
            for record in chain.records:
                status = await self.verify_record(record.id)
                results[record.id] = status
            
            return results

    async def verify_integrity(self) -> Dict[str, Any]:
        async with self._lock:
            results = {
                "chains": {},
                "records": {},
                "trust_anchors": {},
                "summary": {
                    "total_records": 0,
                    "verified": 0,
                    "failed": 0,
                    "tampered": 0,
                    "corrupted": 0,
                }
            }
            
            for chain_id, chain in self._chains.items():
                chain_results = await self.verify_chain(chain_id)
                results["chains"][chain_id] = {
                    "name": chain.name,
                    "size": chain.size,
                    "last_hash": chain.last_hash,
                    "records": chain_results
                }
            
            for record_id, record in self._records.items():
                results["records"][record_id] = record.integrity_status.value
                
                if record.integrity_status == IntegrityStatus.VERIFIED:
                    results["summary"]["verified"] += 1
                elif record.integrity_status == IntegrityStatus.FAILED:
                    results["summary"]["failed"] += 1
                elif record.integrity_status == IntegrityStatus.TAMPERED:
                    results["summary"]["tampered"] += 1
                elif record.integrity_status == IntegrityStatus.CORRUPTED:
                    results["summary"]["corrupted"] += 1
                results["summary"]["total_records"] += 1
            
            return results

    async def compute_merkle_root(self, chain_id: str) -> Optional[str]:
        async with self._lock:
            if chain_id not in self._chains:
                return None
            
            chain = self._chains[chain_id]
            hashes = [record.hash for record in chain.records]
            return self._crypto.compute_merkle_root(hashes)

    async def generate_merkle_proof(self, chain_id: str, record_id: str) -> Optional[List[str]]:
        async with self._lock:
            if chain_id not in self._chains:
                return None
            
            chain = self._chains[chain_id]
            
            record_index = None
            for i, record in enumerate(chain.records):
                if record.id == record_id:
                    record_index = i
                    break
            
            if record_index is None:
                return None
            
            hashes = [record.hash for record in chain.records]
            return self._crypto.compute_merkle_proof(hashes, record_index)

    async def verify_merkle_proof(self, record_id: str, proof: List[str], root_hash: str) -> bool:
        async with self._lock:
            if record_id not in self._records:
                return False
            
            record = self._records[record_id]
            return self._crypto.verify_merkle_proof(proof, record.hash, root_hash)

    async def add_trust_anchor(self, anchor: TrustAnchor) -> None:
        async with self._lock:
            self._trust_anchors[anchor.id] = anchor

    async def revoke_trust_anchor(self, anchor_id: str) -> None:
        async with self._lock:
            if anchor_id in self._trust_anchors:
                self._trust_anchors[anchor_id].revoked = True

    async def get_chain(self, chain_id: str) -> Optional[ProvenanceChain]:
        async with self._lock:
            return self._chains.get(chain_id)

    async def get_record(self, record_id: str) -> Optional[ProvenanceRecord]:
        async with self._lock:
            return self._records.get(record_id)

    async def get_records_by_type(self, record_type: ProvenanceType) -> List[ProvenanceRecord]:
        async with self._lock:
            return [r for r in self._records.values() if r.type == record_type]

    async def get_records_by_source(self, source: str) -> List[ProvenanceRecord]:
        async with self._lock:
            return [r for r in self._records.values() if r.source == source]

    async def get_records_by_time_range(self, start: float, end: float) -> List[ProvenanceRecord]:
        async with self._lock:
            return [r for r in self._records.values() if start <= r.timestamp <= end]

    async def export_chain(self, chain_id: str, format: str = "json") -> Optional[bytes]:
        async with self._lock:
            if chain_id not in self._chains:
                return None
            
            chain = self._chains[chain_id]
            
            if format == "json":
                data = {
                    "id": chain.id,
                    "name": chain.name,
                    "created_at": chain.created_at,
                    "updated_at": chain.updated_at,
                    "size": chain.size,
                    "last_hash": chain.last_hash,
                    "metadata": chain.metadata,
                    "records": [
                        {
                            "id": r.id,
                            "type": r.type.value,
                            "timestamp": r.timestamp,
                            "source": r.source,
                            "hash": r.hash,
                            "signature": base64.b64encode(r.signature).decode(),
                            "signer": r.signer,
                            "algorithm": r.algorithm.value,
                            "previous_hash": r.previous_hash,
                            "integrity_status": r.integrity_status.value,
                            "metadata": r.metadata,
                            "verification_time": r.verification_time
                        }
                        for r in chain.records
                    ]
                }
                return json.dumps(data, indent=2).encode()
            
            elif format == "protobuf":
                data = pickle.dumps(chain)
                return zlib.compress(data)
            
            else:
                raise ValueError(f"Unsupported export format: {format}")

    async def import_chain(self, data: bytes, format: str = "json") -> Optional[str]:
        async with self._lock:
            if format == "json":
                chain_data = json.loads(data)
                chain = ProvenanceChain(
                    id=chain_data["id"],
                    name=chain_data["name"],
                    records=[],
                    created_at=chain_data["created_at"],
                    updated_at=chain_data["updated_at"],
                    last_hash=chain_data["last_hash"],
                    size=chain_data["size"],
                    metadata=chain_data.get("metadata", {})
                )
                
                for record_data in chain_data["records"]:
                    record = ProvenanceRecord(
                        id=record_data["id"],
                        type=ProvenanceType(record_data["type"]),
                        data=None,
                        timestamp=record_data["timestamp"],
                        source=record_data["source"],
                        hash=record_data["hash"],
                        signature=base64.b64decode(record_data["signature"]),
                        signer=record_data["signer"],
                        algorithm=SignatureAlgorithm(record_data["algorithm"]),
                        previous_hash=record_data.get("previous_hash"),
                        integrity_status=IntegrityStatus(record_data["integrity_status"]),
                        metadata=record_data.get("metadata", {}),
                        verification_time=record_data.get("verification_time")
                    )
                    chain.records.append(record)
                    self._records[record.id] = record
                
                self._chains[chain.id] = chain
                return chain.id
                
            elif format == "protobuf":
                data = zlib.decompress(data)
                chain = pickle.loads(data)
                self._chains[chain.id] = chain
                for record in chain.records:
                    self._records[record.id] = record
                return chain.id
                
            else:
                raise ValueError(f"Unsupported import format: {format}")

    async def save_state(self) -> None:
        if not self._storage_path:
            return
        
        state = {
            "chains": self._chains,
            "records": self._records,
            "trust_anchors": self._trust_anchors,
            "timestamp": time.time()
        }
        
        data = pickle.dumps(state)
        compressed = zlib.compress(data)
        
        filepath = os.path.join(self._storage_path, "provenance_state.dat")
        with open(filepath, "wb") as f:
            f.write(compressed)

    async def load_state(self) -> bool:
        if not self._storage_path:
            return False
        
        filepath = os.path.join(self._storage_path, "provenance_state.dat")
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, "rb") as f:
                compressed = f.read()
            
            data = zlib.decompress(compressed)
            state = pickle.loads(data)
            
            self._chains = state["chains"]
            self._records = state["records"]
            self._trust_anchors = state["trust_anchors"]
            
            return True
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            return False


class HedgeBotProvenance:
    
    def __init__(self, chain_name: str = "hedge_bot_provenance"):
        self.chain_manager = ProvenanceChainManager()
        self.chain_id: Optional[str] = None
        self.chain_name = chain_name
        self._lock = asyncio.Lock()
        self._handlers: Dict[ProvenanceType, List[Callable]] = defaultdict(list)
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._buffer: List[ProvenanceRecord] = []
        self._buffer_size = 100
        self._flush_interval = 60
        self._last_flush = time.time()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

    async def initialize(self) -> None:
        self.chain_id = await self.chain_manager.create_chain(self.chain_name)
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(f"Provenance chain initialized: {self.chain_id}")

    async def record_trade(
        self,
        trade_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        return await self._record(ProvenanceType.TRADE, trade_data, metadata)

    async def record_order(
        self,
        order_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        return await self._record(ProvenanceType.ORDER, order_data, metadata)

    async def record_signal(
        self,
        signal_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        return await self._record(ProvenanceType.SIGNAL, signal_data, metadata)

    async def record_decision(
        self,
        decision_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        return await self._record(ProvenanceType.DECISION, decision_data, metadata)

    async def record_position(
        self,
        position_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        return await self._record(ProvenanceType.POSITION, position_data, metadata)

    async def record_performance(
        self,
        performance_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        return await self._record(ProvenanceType.PERFORMANCE, performance_data, metadata)

    async def record_risk(
        self,
        risk_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        return await self._record(ProvenanceType.RISK, risk_data, metadata)

    async def record_alert(
        self,
        alert_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        return await self._record(ProvenanceType.ALERT, alert_data, metadata)

    async def record_config(
        self,
        config_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        return await self._record(ProvenanceType.CONFIG, config_data, metadata)

    async def _record(
        self,
        record_type: ProvenanceType,
        data: Any,
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        async with self._lock:
            if not self.chain_id:
                return None
            
            previous_hash = await self._get_last_hash()
            record_id = await self.chain_manager.add_record(
                self.chain_id,
                record_type,
                data,
                "hedge_bot",
                previous_hash,
                metadata
            )
            
            if record_id:
                record = await self.chain_manager.get_record(record_id)
                if record:
                    self._buffer.append(record)
                    await self._trigger_handlers(record_type, record)
                    await self._trigger_event("record_created", {"record_id": record_id, "type": record_type})
                    
                    if len(self._buffer) >= self._buffer_size:
                        await self._flush_buffer()
            
            return record_id

    async def _get_last_hash(self) -> Optional[str]:
        if not self.chain_id:
            return None
        
        chain = await self.chain_manager.get_chain(self.chain_id)
        return chain.last_hash if chain else None

    async def _flush_buffer(self) -> None:
        if not self._buffer:
            return
        
        async with self._lock:
            self._buffer.clear()
            self._last_flush = time.time()
            await self.chain_manager.save_state()
            await self._trigger_event("buffer_flushed", {"count": len(self._buffer)})

    async def _flush_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                if time.time() - self._last_flush >= self._flush_interval:
                    await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")
                await asyncio.sleep(1)

    async def _trigger_handlers(self, record_type: ProvenanceType, record: ProvenanceRecord) -> None:
        for handler in self._handlers.get(record_type, []):
            try:
                await handler(record)
            except Exception as e:
                logger.error(f"Error in handler for {record_type}: {e}")

    async def _trigger_event(self, event_name: str, data: Any) -> None:
        for handler in self._event_handlers.get(event_name, []):
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"Error in event handler {event_name}: {e}")

    def register_handler(self, record_type: ProvenanceType, handler: Callable) -> None:
        self._handlers[record_type].append(handler)

    def register_event_handler(self, event_name: str, handler: Callable) -> None:
        self._event_handlers[event_name].append(handler)

    async def verify_record(self, record_id: str) -> IntegrityStatus:
        return await self.chain_manager.verify_record(record_id)

    async def verify_chain(self) -> Dict[str, IntegrityStatus]:
        if not self.chain_id:
            return {}
        return await self.chain_manager.verify_chain(self.chain_id)

    async def verify_integrity(self) -> Dict[str, Any]:
        return await self.chain_manager.verify_integrity()

    async def get_record(self, record_id: str) -> Optional[ProvenanceRecord]:
        return await self.chain_manager.get_record(record_id)

    async def get_records_by_type(self, record_type: ProvenanceType) -> List[ProvenanceRecord]:
        return await self.chain_manager.get_records_by_type(record_type)

    async def get_records_by_source(self, source: str) -> List[ProvenanceRecord]:
        return await self.chain_manager.get_records_by_source(source)

    async def get_records_by_time_range(self, start: float, end: float) -> List[ProvenanceRecord]:
        return await self.chain_manager.get_records_by_time_range(start, end)

    async def get_merkle_root(self) -> Optional[str]:
        if not self.chain_id:
            return None
        return await self.chain_manager.compute_merkle_root(self.chain_id)

    async def generate_merkle_proof(self, record_id: str) -> Optional[List[str]]:
        if not self.chain_id:
            return None
        return await self.chain_manager.generate_merkle_proof(self.chain_id, record_id)

    async def verify_merkle_proof(self, record_id: str, proof: List[str], root_hash: str) -> bool:
        return await self.chain_manager.verify_merkle_proof(record_id, proof, root_hash)

    async def export_chain(self, format: str = "json") -> Optional[bytes]:
        if not self.chain_id:
            return None
        return await self.chain_manager.export_chain(self.chain_id, format)

    async def import_chain(self, data: bytes, format: str = "json") -> Optional[str]:
        return await self.chain_manager.import_chain(data, format)

    async def save_state(self) -> None:
        await self.chain_manager.save_state()

    async def load_state(self) -> bool:
        return await self.chain_manager.load_state()

    async def shutdown(self) -> None:
        self._running = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        
        await self._flush_buffer()
        await self.save_state()
        logger.info("Provenance system shutdown")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "chain_name": self.chain_name,
            "running": self._running,
            "buffer_size": len(self._buffer),
            "buffer_max": self._buffer_size,
            "flush_interval": self._flush_interval,
            "last_flush": self._last_flush,
            "registered_handlers": len(self._handlers),
            "registered_event_handlers": len(self._event_handlers),
            "total_records": len(self.chain_manager._records) if self.chain_manager else 0,
        }


class ProvenanceAudit:
    
    def __init__(self, provenance: HedgeBotProvenance):
        self.provenance = provenance
        self._lock = asyncio.Lock()
        self._audit_trail: List[Dict[str, Any]] = []
        self._max_audit_size = 10000

    async def log(
        self,
        action: str,
        resource: str,
        data: Any,
        user: str = "system",
        ip: str = "127.0.0.1",
        metadata: Dict[str, Any] = None
    ) -> None:
        async with self._lock:
            entry = {
                "timestamp": time.time(),
                "action": action,
                "resource": resource,
                "data": data,
                "user": user,
                "ip": ip,
                "metadata": metadata or {}
            }
            
            self._audit_trail.append(entry)
            
            if len(self._audit_trail) > self._max_audit_size:
                self._audit_trail = self._audit_trail[-self._max_audit_size:]
            
            await self.provenance.record_alert(
                {
                    "type": "audit",
                    "action": action,
                    "resource": resource,
                    "user": user,
                    "ip": ip
                },
                metadata
            )

    async def get_audit_trail(
        self,
        start: Optional[float] = None,
        end: Optional[float] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        user: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        async with self._lock:
            results = self._audit_trail
            
            if start:
                results = [e for e in results if e["timestamp"] >= start]
            if end:
                results = [e for e in results if e["timestamp"] <= end]
            if action:
                results = [e for e in results if e["action"] == action]
            if resource:
                results = [e for e in results if e["resource"] == resource]
            if user:
                results = [e for e in results if e["user"] == user]
            
            return results[-limit:] if len(results) > limit else results

    async def get_stats(self) -> Dict[str, Any]:
        async with self._lock:
            return {
                "total_entries": len(self._audit_trail),
                "max_size": self._max_audit_size,
                "unique_actions": len(set(e["action"] for e in self._audit_trail)),
                "unique_resources": len(set(e["resource"] for e in self._audit_trail)),
                "unique_users": len(set(e["user"] for e in self._audit_trail)),
            }


__all__ = [
    "ProvenanceType",
    "IntegrityStatus",
    "SignatureAlgorithm",
    "ProvenanceRecord",
    "ProvenanceChain",
    "ProvenanceProof",
    "TrustAnchor",
    "CryptographicUtils",
    "ProvenanceChainManager",
    "HedgeBotProvenance",
    "ProvenanceAudit",
]
