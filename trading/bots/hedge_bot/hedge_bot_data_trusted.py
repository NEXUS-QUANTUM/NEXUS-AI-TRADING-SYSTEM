# trading/bots/hedge_bot/hedge_bot_data_trusted.py

import asyncio
import logging
import time
import json
import hashlib
import base64
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

logger = logging.getLogger(__name__)


class TrustLevel(str, Enum):
    UNTRUSTED = "untrusted"
    BASIC = "basic"
    VERIFIED = "verified"
    TRUSTED = "trusted"
    HIGHLY_TRUSTED = "highly_trusted"
    INSTITUTIONAL = "institutional"


class TrustStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    ACTIVE = "active"


@dataclass
class TrustedEntity:
    id: str
    name: str
    trust_level: TrustLevel
    status: TrustStatus
    public_key: Optional[bytes] = None
    certificate: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    verified_by: Optional[str] = None


@dataclass
class TrustedData:
    id: str
    entity_id: str
    data: Any
    signature: bytes
    timestamp: float
    hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    trust_level: TrustLevel = TrustLevel.BASIC


@dataclass
class TrustVerification:
    id: str
    data_id: str
    entity_id: str
    verified: bool
    timestamp: float
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrustChain:
    id: str
    name: str
    entities: List[str]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataTrustManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._entities: Dict[str, TrustedEntity] = {}
        self._trusted_data: Dict[str, TrustedData] = {}
        self._verifications: Dict[str, TrustVerification] = {}
        self._chains: Dict[str, TrustChain] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_entities()

    def _initialize_default_entities(self) -> None:
        default_entities = [
            TrustedEntity(
                id="nexus_root",
                name="NEXUS Root Authority",
                trust_level=TrustLevel.INSTITUTIONAL,
                status=TrustStatus.ACTIVE
            ),
            TrustedEntity(
                id="nexus_core",
                name="NEXUS Core Service",
                trust_level=TrustLevel.HIGHLY_TRUSTED,
                status=TrustStatus.ACTIVE,
                verified_by="nexus_root"
            ),
            TrustedEntity(
                id="nexus_hedge_bot",
                name="NEXUS Hedge Bot",
                trust_level=TrustLevel.TRUSTED,
                status=TrustStatus.ACTIVE,
                verified_by="nexus_core"
            )
        ]
        
        for entity in default_entities:
            self._entities[entity.id] = entity

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_entity(
        self,
        name: str,
        trust_level: TrustLevel,
        public_key: Optional[bytes] = None,
        certificate: Optional[bytes] = None,
        verified_by: Optional[str] = None,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TrustedEntity:
        async with self._lock:
            entity_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            entity = TrustedEntity(
                id=entity_id,
                name=name,
                trust_level=trust_level,
                status=TrustStatus.PENDING,
                public_key=public_key,
                certificate=certificate,
                metadata=metadata or {},
                expires_at=time.time() + expires_in if expires_in else None,
                verified_by=verified_by
            )
            
            self._entities[entity_id] = entity
            
            if verified_by:
                await self._verify_entity(entity_id, verified_by)
            
            await self._notify_observers("entity_added", entity)
            return entity

    async def _verify_entity(self, entity_id: str, verifier_id: str) -> bool:
        if entity_id not in self._entities:
            return False
        
        if verifier_id not in self._entities:
            return False
        
        entity = self._entities[entity_id]
        verifier = self._entities[verifier_id]
        
        if verifier.trust_level.value < TrustLevel.VERIFIED.value:
            return False
        
        entity.status = TrustStatus.VERIFIED
        entity.verified_by = verifier_id
        entity.updated_at = time.time()
        
        await self._notify_observers("entity_verified", entity)
        return True

    async def verify_data(
        self,
        entity_id: str,
        data: Any,
        signature: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[TrustVerification]:
        async with self._lock:
            if entity_id not in self._entities:
                return None
            
            entity = self._entities[entity_id]
            
            if entity.status != TrustStatus.ACTIVE:
                return None
            
            data_hash = hashlib.sha256(json.dumps(data, default=str).encode()).hexdigest()
            
            is_valid = await self._verify_signature(data, signature, entity)
            
            verification = TrustVerification(
                id=hashlib.md5(f"{entity_id}_{time.time()}".encode()).hexdigest(),
                data_id=data_hash,
                entity_id=entity_id,
                verified=is_valid,
                timestamp=time.time(),
                reason="Signature verified" if is_valid else "Signature verification failed",
                metadata=metadata or {}
            )
            
            self._verifications[verification.id] = verification
            
            if is_valid:
                trusted_data = TrustedData(
                    id=hashlib.md5(f"{data_hash}_{time.time()}".encode()).hexdigest(),
                    entity_id=entity_id,
                    data=data,
                    signature=signature,
                    timestamp=time.time(),
                    hash=data_hash,
                    metadata=metadata or {},
                    trust_level=entity.trust_level
                )
                
                self._trusted_data[trusted_data.id] = trusted_data
                await self._notify_observers("data_verified", trusted_data)
            
            await self._notify_observers("verification_completed", verification)
            return verification

    async def _verify_signature(
        self,
        data: Any,
        signature: bytes,
        entity: TrustedEntity
    ) -> bool:
        if not CRYPTOGRAPHY_AVAILABLE:
            return True
        
        if not entity.public_key:
            return False
        
        data_bytes = json.dumps(data, default=str).encode()
        
        try:
            public_key = serialization.load_pem_public_key(entity.public_key)
            public_key.verify(signature, data_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    async def create_trust_chain(
        self,
        name: str,
        entity_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[TrustChain]:
        async with self._lock:
            for entity_id in entity_ids:
                if entity_id not in self._entities:
                    return None
            
            chain = TrustChain(
                id=hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest(),
                name=name,
                entities=entity_ids,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self._chains[chain.id] = chain
            await self._notify_observers("chain_created", chain)
            return chain

    async def get_entity(self, entity_id: str) -> Optional[TrustedEntity]:
        return self._entities.get(entity_id)

    async def get_entities(self) -> List[TrustedEntity]:
        return list(self._entities.values())

    async def get_trusted_data(self, data_id: str) -> Optional[TrustedData]:
        return self._trusted_data.get(data_id)

    async def get_trusted_data_by_entity(self, entity_id: str) -> List[TrustedData]:
        return [d for d in self._trusted_data.values() if d.entity_id == entity_id]

    async def get_verification(self, verification_id: str) -> Optional[TrustVerification]:
        return self._verifications.get(verification_id)

    async def get_chain(self, chain_id: str) -> Optional[TrustChain]:
        return self._chains.get(chain_id)

    async def get_chains(self) -> List[TrustChain]:
        return list(self._chains.values())

    async def revoke_entity(self, entity_id: str, reason: str) -> bool:
        if entity_id in self._entities:
            self._entities[entity_id].status = TrustStatus.REVOKED
            self._entities[entity_id].metadata["revocation_reason"] = reason
            self._entities[entity_id].updated_at = time.time()
            await self._notify_observers("entity_revoked", entity_id)
            return True
        return False

    async def suspend_entity(self, entity_id: str, reason: str) -> bool:
        if entity_id in self._entities:
            self._entities[entity_id].status = TrustStatus.SUSPENDED
            self._entities[entity_id].metadata["suspension_reason"] = reason
            self._entities[entity_id].updated_at = time.time()
            await self._notify_observers("entity_suspended", entity_id)
            return True
        return False

    async def activate_entity(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            self._entities[entity_id].status = TrustStatus.ACTIVE
            self._entities[entity_id].updated_at = time.time()
            await self._notify_observers("entity_activated", entity_id)
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
            "entities": len(self._entities),
            "trusted_data": len(self._trusted_data),
            "verifications": len(self._verifications),
            "chains": len(self._chains),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "TrustLevel",
    "TrustStatus",
    "TrustedEntity",
    "TrustedData",
    "TrustVerification",
    "TrustChain",
    "DataTrustManager"
]
