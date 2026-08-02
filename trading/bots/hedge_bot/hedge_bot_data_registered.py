# trading/bots/hedge_bot/hedge_bot_data_registered.py

import asyncio
import logging
import time
import json
import hashlib
import base64
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import pickle
import zlib
import re

logger = logging.getLogger(__name__)


class RegistrationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    DELETED = "deleted"


class RegistrationType(str, Enum):
    USER = "user"
    DEVICE = "device"
    SERVICE = "service"
    API_KEY = "api_key"
    BROKER = "broker"
    BOT = "bot"
    STRATEGY = "strategy"
    WEBHOOK = "webhook"
    SIGNAL = "signal"
    SUBSCRIPTION = "subscription"
    LICENSE = "license"
    CERTIFICATE = "certificate"
    IDENTITY = "identity"
    CONTACT = "contact"
    ADDRESS = "address"
    BANK = "bank"
    PAYMENT = "payment"


class VerificationLevel(str, Enum):
    NONE = "none"
    BASIC = "basic"
    EMAIL = "email"
    PHONE = "phone"
    IDENTITY = "identity"
    KYC = "kyc"
    AML = "aml"
    ADVANCED = "advanced"
    PREMIUM = "premium"
    INSTITUTIONAL = "institutional"


class RegistrationSource(str, Enum):
    WEB = "web"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    API = "api"
    CLI = "cli"
    BOT = "bot"
    INTERNAL = "internal"
    EXTERNAL = "external"
    IMPORT = "import"
    MIGRATION = "migration"


@dataclass
class RegistrationData:
    id: str
    type: RegistrationType
    status: RegistrationStatus
    created_at: float
    updated_at: float
    expires_at: Optional[float] = None
    verified_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    hash: Optional[str] = None
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    source: RegistrationSource = RegistrationSource.INTERNAL


@dataclass
class UserRegistration(RegistrationData):
    username: str
    email: str
    password_hash: str
    first_name: str
    last_name: str
    verification_level: VerificationLevel = VerificationLevel.NONE
    last_login: Optional[float] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)


@dataclass
class DeviceRegistration(RegistrationData):
    device_id: str
    device_name: str
    device_type: str
    os: str
    os_version: str
    app_version: str
    ip_address: str
    user_agent: str
    fingerprint: str
    last_seen: Optional[float] = None
    trusted: bool = False


@dataclass
class ServiceRegistration(RegistrationData):
    service_name: str
    service_type: str
    endpoint: str
    protocol: str
    version: str
    health_check_url: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIKeyRegistration(RegistrationData):
    key: str
    name: str
    permissions: List[str]
    rate_limit: int
    allowed_ips: List[str] = field(default_factory=list)
    allowed_origins: List[str] = field(default_factory=list)
    last_used: Optional[float] = None
    usage_count: int = 0


@dataclass
class BrokerRegistration(RegistrationData):
    broker_name: str
    broker_type: str
    account_id: str
    api_key: str
    api_secret: str
    is_production: bool = False
    margin_available: Decimal = Decimal('0')
    leverage: Decimal = Decimal('1')
    supported_assets: List[str] = field(default_factory=list)
    connection_status: str = "disconnected"


@dataclass
class BotRegistration(RegistrationData):
    bot_name: str
    bot_type: str
    strategy_id: str
    version: str
    status: str = "stopped"
    config: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[float] = None
    stop_time: Optional[float] = None


@dataclass
class SubscriptionRegistration(RegistrationData):
    plan: str
    tier: str
    features: List[str]
    price: Decimal
    currency: str
    billing_cycle: str
    auto_renew: bool = True
    renewal_date: Optional[float] = None
    payment_method: Optional[str] = None
    trial_ends: Optional[float] = None


@dataclass
class LicenseRegistration(RegistrationData):
    license_key: str
    product: str
    edition: str
    seats: int
    used_seats: int
    features: List[str]
    issuer: str
    signature: Optional[str] = None


class DataRegistry:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._registrations: Dict[str, RegistrationData] = {}
        self._indices: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300
        self._validators: Dict[RegistrationType, Callable] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._id_counter = 0
        
        self._initialize_validators()
        self._initialize_default_registrations()

    def _initialize_validators(self) -> None:
        self.register_validator(RegistrationType.USER, self._validate_user)
        self.register_validator(RegistrationType.DEVICE, self._validate_device)
        self.register_validator(RegistrationType.SERVICE, self._validate_service)
        self.register_validator(RegistrationType.API_KEY, self._validate_api_key)
        self.register_validator(RegistrationType.BROKER, self._validate_broker)
        self.register_validator(RegistrationType.BOT, self._validate_bot)
        self.register_validator(RegistrationType.SUBSCRIPTION, self._validate_subscription)
        self.register_validator(RegistrationType.LICENSE, self._validate_license)

    def _initialize_default_registrations(self) -> None:
        pass

    def register_validator(self, reg_type: RegistrationType, validator: Callable) -> None:
        self._validators[reg_type] = validator

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def _generate_id(self) -> str:
        self._id_counter += 1
        return f"reg_{int(time.time())}_{self._id_counter:06d}"

    async def _compute_hash(self, data: Dict[str, Any]) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    async def register(
        self,
        reg_type: RegistrationType,
        data: Dict[str, Any],
        source: RegistrationSource = RegistrationSource.INTERNAL,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        ttl: Optional[int] = None
    ) -> Optional[RegistrationData]:
        async with self._lock:
            if reg_type in self._validators:
                validation_result = await self._validators[reg_type](data)
                if not validation_result.get("valid", False):
                    logger.warning(f"Validation failed: {validation_result.get('reason', 'Unknown')}")
                    return None
            
            reg_id = await self._generate_id()
            timestamp = time.time()
            
            registration_data = {
                "id": reg_id,
                "type": reg_type,
                "status": RegistrationStatus.PENDING,
                "created_at": timestamp,
                "updated_at": timestamp,
                "expires_at": timestamp + ttl if ttl else None,
                "metadata": metadata or {},
                "version": 1,
                "parent_id": parent_id,
                "children": [],
                "tags": tags or [],
                "source": source
            }
            
            registration_data.update(data)
            
            hash_value = await self._compute_hash(registration_data)
            registration_data["hash"] = hash_value
            
            registration = self._create_registration_object(reg_type, registration_data)
            
            self._registrations[reg_id] = registration
            await self._update_indices(registration)
            
            if parent_id and parent_id in self._registrations:
                self._registrations[parent_id].children.append(reg_id)
            
            await self._notify_observers("registered", registration)
            
            return registration

    def _create_registration_object(
        self,
        reg_type: RegistrationType,
        data: Dict[str, Any]
    ) -> RegistrationData:
        if reg_type == RegistrationType.USER:
            return UserRegistration(**data)
        elif reg_type == RegistrationType.DEVICE:
            return DeviceRegistration(**data)
        elif reg_type == RegistrationType.SERVICE:
            return ServiceRegistration(**data)
        elif reg_type == RegistrationType.API_KEY:
            return APIKeyRegistration(**data)
        elif reg_type == RegistrationType.BROKER:
            return BrokerRegistration(**data)
        elif reg_type == RegistrationType.BOT:
            return BotRegistration(**data)
        elif reg_type == RegistrationType.SUBSCRIPTION:
            return SubscriptionRegistration(**data)
        elif reg_type == RegistrationType.LICENSE:
            return LicenseRegistration(**data)
        else:
            return RegistrationData(**data)

    async def update(
        self,
        reg_id: str,
        data: Dict[str, Any],
        update_hash: bool = True
    ) -> Optional[RegistrationData]:
        async with self._lock:
            if reg_id not in self._registrations:
                return None
            
            registration = self._registrations[reg_id]
            
            for key, value in data.items():
                if hasattr(registration, key):
                    setattr(registration, key, value)
            
            registration.updated_at = time.time()
            registration.version += 1
            
            if update_hash:
                registration.hash = await self._compute_hash(registration.__dict__)
            
            await self._update_indices(registration)
            await self._notify_observers("updated", registration)
            
            return registration

    async def update_status(
        self,
        reg_id: str,
        status: RegistrationStatus,
        reason: Optional[str] = None
    ) -> Optional[RegistrationData]:
        async with self._lock:
            if reg_id not in self._registrations:
                return None
            
            registration = self._registrations[reg_id]
            old_status = registration.status
            registration.status = status
            registration.updated_at = time.time()
            registration.version += 1
            
            if status == RegistrationStatus.APPROVED:
                registration.verified_at = time.time()
            elif status == RegistrationStatus.REJECTED:
                registration.metadata["rejection_reason"] = reason
            
            await self._notify_observers("status_changed", registration, old_status)
            
            return registration

    async def get(self, reg_id: str) -> Optional[RegistrationData]:
        return self._registrations.get(reg_id)

    async def get_by_hash(self, hash_value: str) -> Optional[RegistrationData]:
        for registration in self._registrations.values():
            if registration.hash == hash_value:
                return registration
        return None

    async def get_by_type(self, reg_type: RegistrationType) -> List[RegistrationData]:
        return [r for r in self._registrations.values() if r.type == reg_type]

    async def get_by_status(self, status: RegistrationStatus) -> List[RegistrationData]:
        return [r for r in self._registrations.values() if r.status == status]

    async def get_by_tag(self, tag: str) -> List[RegistrationData]:
        return [r for r in self._registrations.values() if tag in r.tags]

    async def get_by_parent(self, parent_id: str) -> List[RegistrationData]:
        return [r for r in self._registrations.values() if r.parent_id == parent_id]

    async def get_by_type_and_status(
        self,
        reg_type: RegistrationType,
        status: RegistrationStatus
    ) -> List[RegistrationData]:
        return [
            r for r in self._registrations.values()
            if r.type == reg_type and r.status == status
        ]

    async def delete(self, reg_id: str, soft: bool = True) -> bool:
        async with self._lock:
            if reg_id not in self._registrations:
                return False
            
            if soft:
                registration = self._registrations[reg_id]
                registration.status = RegistrationStatus.DELETED
                registration.updated_at = time.time()
                registration.version += 1
                await self._notify_observers("deleted", registration)
            else:
                del self._registrations[reg_id]
                await self._notify_observers("deleted", reg_id)
            
            return True

    async def _update_indices(self, registration: RegistrationData) -> None:
        self._indices["type"][registration.type.value].add(registration.id)
        self._indices["status"][registration.status.value].add(registration.id)
        
        for tag in registration.tags:
            self._indices["tags"][tag].add(registration.id)
        
        if registration.parent_id:
            self._indices["parent"][registration.parent_id].add(registration.id)
        
        if hasattr(registration, "username"):
            self._indices["username"][registration.username].add(registration.id)
        
        if hasattr(registration, "email"):
            self._indices["email"][registration.email].add(registration.id)

    async def _validate_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if "username" not in data or not data["username"]:
            return {"valid": False, "reason": "Username required"}
        
        if "email" not in data or not data["email"]:
            return {"valid": False, "reason": "Email required"}
        
        if "password_hash" not in data or not data["password_hash"]:
            return {"valid": False, "reason": "Password required"}
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, data["email"]):
            return {"valid": False, "reason": "Invalid email format"}
        
        if len(data["username"]) < 3 or len(data["username"]) > 50:
            return {"valid": False, "reason": "Username must be between 3 and 50 characters"}
        
        if "first_name" in data and data["first_name"] and len(data["first_name"]) > 100:
            return {"valid": False, "reason": "First name too long"}
        
        if "last_name" in data and data["last_name"] and len(data["last_name"]) > 100:
            return {"valid": False, "reason": "Last name too long"}
        
        return {"valid": True}

    async def _validate_device(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if "device_id" not in data or not data["device_id"]:
            return {"valid": False, "reason": "Device ID required"}
        
        if "device_name" not in data or not data["device_name"]:
            return {"valid": False, "reason": "Device name required"}
        
        if "device_type" not in data or not data["device_type"]:
            return {"valid": False, "reason": "Device type required"}
        
        if "fingerprint" not in data or not data["fingerprint"]:
            return {"valid": False, "reason": "Fingerprint required"}
        
        return {"valid": True}

    async def _validate_service(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if "service_name" not in data or not data["service_name"]:
            return {"valid": False, "reason": "Service name required"}
        
        if "service_type" not in data or not data["service_type"]:
            return {"valid": False, "reason": "Service type required"}
        
        if "endpoint" not in data or not data["endpoint"]:
            return {"valid": False, "reason": "Endpoint required"}
        
        if "protocol" not in data or not data["protocol"]:
            return {"valid": False, "reason": "Protocol required"}
        
        return {"valid": True}

    async def _validate_api_key(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if "name" not in data or not data["name"]:
            return {"valid": False, "reason": "Name required"}
        
        if "permissions" not in data or not data["permissions"]:
            return {"valid": False, "reason": "Permissions required"}
        
        if "rate_limit" not in data or data["rate_limit"] <= 0:
            return {"valid": False, "reason": "Rate limit must be positive"}
        
        return {"valid": True}

    async def _validate_broker(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if "broker_name" not in data or not data["broker_name"]:
            return {"valid": False, "reason": "Broker name required"}
        
        if "broker_type" not in data or not data["broker_type"]:
            return {"valid": False, "reason": "Broker type required"}
        
        if "account_id" not in data or not data["account_id"]:
            return {"valid": False, "reason": "Account ID required"}
        
        if "api_key" not in data or not data["api_key"]:
            return {"valid": False, "reason": "API key required"}
        
        if "api_secret" not in data or not data["api_secret"]:
            return {"valid": False, "reason": "API secret required"}
        
        return {"valid": True}

    async def _validate_bot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if "bot_name" not in data or not data["bot_name"]:
            return {"valid": False, "reason": "Bot name required"}
        
        if "bot_type" not in data or not data["bot_type"]:
            return {"valid": False, "reason": "Bot type required"}
        
        if "strategy_id" not in data or not data["strategy_id"]:
            return {"valid": False, "reason": "Strategy ID required"}
        
        return {"valid": True}

    async def _validate_subscription(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if "plan" not in data or not data["plan"]:
            return {"valid": False, "reason": "Plan required"}
        
        if "tier" not in data or not data["tier"]:
            return {"valid": False, "reason": "Tier required"}
        
        if "features" not in data or not data["features"]:
            return {"valid": False, "reason": "Features required"}
        
        if "price" not in data or data["price"] < 0:
            return {"valid": False, "reason": "Price must be non-negative"}
        
        if "currency" not in data or not data["currency"]:
            return {"valid": False, "reason": "Currency required"}
        
        return {"valid": True}

    async def _validate_license(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if "license_key" not in data or not data["license_key"]:
            return {"valid": False, "reason": "License key required"}
        
        if "product" not in data or not data["product"]:
            return {"valid": False, "reason": "Product required"}
        
        if "edition" not in data or not data["edition"]:
            return {"valid": False, "reason": "Edition required"}
        
        if "seats" not in data or data["seats"] <= 0:
            return {"valid": False, "reason": "Seats must be positive"}
        
        return {"valid": True}

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    async def count(self, reg_type: Optional[RegistrationType] = None) -> int:
        if reg_type:
            return len([r for r in self._registrations.values() if r.type == reg_type])
        return len(self._registrations)

    async def search(self, query: Dict[str, Any]) -> List[RegistrationData]:
        results = []
        
        for registration in self._registrations.values():
            match = True
            for key, value in query.items():
                if not hasattr(registration, key):
                    match = False
                    break
                if getattr(registration, key) != value:
                    match = False
                    break
            if match:
                results.append(registration)
        
        return results

    async def export(self, reg_id: str) -> Optional[Dict[str, Any]]:
        if reg_id not in self._registrations:
            return None
        
        registration = self._registrations[reg_id]
        return registration.__dict__

    async def import_registration(
        self,
        data: Dict[str, Any],
        reg_type: Optional[RegistrationType] = None
    ) -> Optional[RegistrationData]:
        if not reg_type and "type" in data:
            reg_type = RegistrationType(data["type"])
        elif not reg_type:
            return None
        
        return await self.register(reg_type, data, source=RegistrationSource.IMPORT)

    def get_stats(self) -> Dict[str, Any]:
        stats = {
            "total": len(self._registrations),
            "by_type": defaultdict(int),
            "by_status": defaultdict(int),
            "cache_size": len(self._cache),
            "running": self._running
        }
        
        for registration in self._registrations.values():
            stats["by_type"][registration.type.value] += 1
            stats["by_status"][registration.status.value] += 1
        
        return dict(stats)

    def clear_cache(self) -> None:
        self._cache.clear()


__all__ = [
    "RegistrationStatus",
    "RegistrationType",
    "VerificationLevel",
    "RegistrationSource",
    "RegistrationData",
    "UserRegistration",
    "DeviceRegistration",
    "ServiceRegistration",
    "APIKeyRegistration",
    "BrokerRegistration",
    "BotRegistration",
    "SubscriptionRegistration",
    "LicenseRegistration",
    "DataRegistry"
]
