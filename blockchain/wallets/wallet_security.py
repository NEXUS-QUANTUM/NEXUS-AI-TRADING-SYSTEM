"""
NEXUS AI TRADING SYSTEM - WALLET SECURITY MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de sécurité avancée pour wallets multi-blockchain.
Chiffrement, authentification, autorisation, audit, et protection contre les menaces.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import bcrypt
import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from eth_account import Account
from web3 import Web3

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction,
    TransactionType,
    TransactionStatus,
    BlockchainNetwork,
    WalletStatus,
    WalletType
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class SecurityLevel(Enum):
    """Niveaux de sécurité."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    MAXIMUM = "maximum"


class SecurityEventType(Enum):
    """Types d'événements de sécurité."""
    LOGIN = "login"
    LOGOUT = "logout"
    FAILED_LOGIN = "failed_login"
    PASSWORD_CHANGE = "password_change"
    TWO_FACTOR_ENABLE = "two_factor_enable"
    TWO_FACTOR_DISABLE = "two_factor_disable"
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"
    TRANSACTION_SIGN = "transaction_sign"
    TRANSACTION_BROADCAST = "transaction_broadcast"
    WHITELIST_ADD = "whitelist_add"
    WHITELIST_REMOVE = "whitelist_remove"
    IP_WHITELIST_ADD = "ip_whitelist_add"
    IP_WHITELIST_REMOVE = "ip_whitelist_remove"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SECURITY_BREACH = "security_breach"
    CONFIG_CHANGE = "config_change"


class TwoFactorMethod(Enum):
    """Méthodes de double authentification."""
    AUTHENTICATOR = "authenticator"
    SMS = "sms"
    EMAIL = "email"
    HARDWARE = "hardware"
    BACKUP_CODE = "backup_code"


@dataclass
class SecurityConfig:
    """Configuration de sécurité."""
    wallet_id: UUID
    user_id: UUID
    security_level: SecurityLevel = SecurityLevel.HIGH
    two_factor_enabled: bool = False
    two_factor_method: Optional[TwoFactorMethod] = None
    two_factor_secret: Optional[str] = None
    backup_codes: List[str] = field(default_factory=list)
    whitelist_enabled: bool = False
    whitelist_addresses: List[str] = field(default_factory=list)
    ip_whitelist_enabled: bool = False
    ip_whitelist: List[str] = field(default_factory=list)
    session_timeout_minutes: int = 60
    max_transaction_amount: Decimal = Decimal("10000")
    daily_transaction_limit: Decimal = Decimal("50000")
    require_confirmation: bool = True
    confirmation_threshold: int = 2
    suspicious_activity_alert: bool = True
    encryption_enabled: bool = True
    encryption_algorithm: str = "AES-256-GCM"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "security_level": self.security_level.value,
            "two_factor_enabled": self.two_factor_enabled,
            "two_factor_method": self.two_factor_method.value if self.two_factor_method else None,
            "two_factor_secret": self.two_factor_secret,
            "backup_codes": self.backup_codes,
            "whitelist_enabled": self.whitelist_enabled,
            "whitelist_addresses": self.whitelist_addresses,
            "ip_whitelist_enabled": self.ip_whitelist_enabled,
            "ip_whitelist": self.ip_whitelist,
            "session_timeout_minutes": self.session_timeout_minutes,
            "max_transaction_amount": str(self.max_transaction_amount),
            "daily_transaction_limit": str(self.daily_transaction_limit),
            "require_confirmation": self.require_confirmation,
            "confirmation_threshold": self.confirmation_threshold,
            "suspicious_activity_alert": self.suspicious_activity_alert,
            "encryption_enabled": self.encryption_enabled,
            "encryption_algorithm": self.encryption_algorithm,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class SecurityEvent:
    """Événement de sécurité."""
    event_id: UUID
    wallet_id: UUID
    user_id: UUID
    event_type: SecurityEventType
    severity: str  # info, warning, critical
    description: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "event_id": str(self.event_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "event_type": self.event_type.value,
            "severity": self.severity,
            "description": self.description,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class APIKey:
    """Clé API."""
    key_id: UUID
    wallet_id: UUID
    user_id: UUID
    name: str
    key: str
    permissions: List[str]
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "key_id": str(self.key_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "key": self.key,
            "permissions": self.permissions,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class Session:
    """Session utilisateur."""
    session_id: UUID
    wallet_id: UUID
    user_id: UUID
    token: str
    refresh_token: str
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "session_id": str(self.session_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "token": self.token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE WALLET SECURITY
# ============================================================================

class WalletSecurity:
    """
    Service de sécurité avancée pour wallets multi-blockchain.
    """

    # Configuration JWT
    JWT_SECRET = secrets.token_hex(32)
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = 24
    REFRESH_TOKEN_EXPIRY_DAYS = 30

    # Seuils de suspicion
    SUSPICIOUS_THRESHOLDS = {
        "max_login_attempts": 5,
        "max_failed_logins_minute": 3,
        "max_transactions_hour": 10,
        "max_amount_change_percent": 50,
        "suspicious_ip_countries": ["RU", "CN", "KP", "IR", "SY"],
        "suspicious_ports": [22, 23, 445, 3389]
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        jwt_secret: Optional[str] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le service de sécurité.

        Args:
            redis_client: Client Redis pour le cache
            jwt_secret: Secret JWT (optionnel)
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.jwt_secret = jwt_secret or self.JWT_SECRET
        self.api_keys = api_keys or {}
        
        # Cache
        self._security_config_cache: Dict[UUID, SecurityConfig] = {}
        self._session_cache: Dict[str, Session] = {}
        self._api_key_cache: Dict[str, APIKey] = {}
        self._event_cache: Dict[UUID, List[SecurityEvent]] = {}
        self._failed_login_cache: Dict[str, int] = {}
        
        # Blacklist
        self._token_blacklist: Set[str] = set()
        
        # Métriques
        self._metrics = {
            "total_events": 0,
            "total_sessions": 0,
            "total_api_keys": 0,
            "security_breaches": 0,
            "suspicious_activities": 0,
            "last_breach": None,
            "by_event_type": {}
        }

        logger.info("WalletSecurity initialisé avec succès")

    # ========================================================================
    # CHIFFREMENT ET DÉCHIFFREMENT
    # ========================================================================

    @staticmethod
    def encrypt_data(
        data: Union[str, bytes],
        key: bytes,
        algorithm: str = "AES-256-GCM"
    ) -> Dict[str, Any]:
        """
        Chiffre des données.

        Args:
            data: Données à chiffrer
            key: Clé de chiffrement
            algorithm: Algorithme de chiffrement

        Returns:
            Données chiffrées avec métadonnées
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')

            if algorithm == "AES-256-GCM":
                iv = os.urandom(12)
                cipher = Cipher(
                    algorithms.AES(key),
                    modes.GCM(iv),
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                encrypted = encryptor.update(data) + encryptor.finalize()
                
                return {
                    "algorithm": algorithm,
                    "iv": base64.b64encode(iv).decode('utf-8'),
                    "tag": base64.b64encode(encryptor.tag).decode('utf-8'),
                    "ciphertext": base64.b64encode(encrypted).decode('utf-8')
                }

            elif algorithm == "AES-256-CBC":
                iv = os.urandom(16)
                cipher = Cipher(
                    algorithms.AES(key),
                    modes.CBC(iv),
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                
                # Padding PKCS7
                pad_len = 16 - (len(data) % 16)
                padded = data + bytes([pad_len] * pad_len)
                
                encrypted = encryptor.update(padded) + encryptor.finalize()
                
                return {
                    "algorithm": algorithm,
                    "iv": base64.b64encode(iv).decode('utf-8'),
                    "ciphertext": base64.b64encode(encrypted).decode('utf-8')
                }

            else:
                raise ValueError(f"Algorithme non supporté: {algorithm}")

        except Exception as e:
            logger.error(f"Erreur lors du chiffrement: {e}")
            raise

    @staticmethod
    def decrypt_data(
        encrypted_data: Dict[str, Any],
        key: bytes
    ) -> bytes:
        """
        Déchiffre des données.

        Args:
            encrypted_data: Données chiffrées avec métadonnées
            key: Clé de chiffrement

        Returns:
            Données déchiffrées
        """
        try:
            algorithm = encrypted_data["algorithm"]
            iv = base64.b64decode(encrypted_data["iv"])
            ciphertext = base64.b64decode(encrypted_data["ciphertext"])

            if algorithm == "AES-256-GCM":
                tag = base64.b64decode(encrypted_data["tag"])
                cipher = Cipher(
                    algorithms.AES(key),
                    modes.GCM(iv, tag),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                return decryptor.update(ciphertext) + decryptor.finalize()

            elif algorithm == "AES-256-CBC":
                cipher = Cipher(
                    algorithms.AES(key),
                    modes.CBC(iv),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                decrypted = decryptor.update(ciphertext) + decryptor.finalize()
                
                # Retrait du padding PKCS7
                pad_len = decrypted[-1]
                return decrypted[:-pad_len]

            else:
                raise ValueError(f"Algorithme non supporté: {algorithm}")

        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement: {e}")
            raise

    @staticmethod
    def derive_key(
        password: str,
        salt: Optional[bytes] = None,
        algorithm: str = "PBKDF2"
    ) -> Tuple[bytes, bytes]:
        """
        Dérive une clé de chiffrement à partir d'un mot de passe.

        Args:
            password: Mot de passe
            salt: Sel (optionnel)
            algorithm: Algorithme de dérivation

        Returns:
            (clé, sel)
        """
        if salt is None:
            salt = os.urandom(32)
        
        password_bytes = password.encode('utf-8')
        
        if algorithm == "PBKDF2":
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
        elif algorithm == "Scrypt":
            kdf = Scrypt(
                salt=salt,
                length=32,
                n=16384,
                r=8,
                p=1,
                backend=default_backend()
            )
        else:
            raise ValueError(f"Algorithme non supporté: {algorithm}")
        
        return kdf.derive(password_bytes), salt

    # ========================================================================
    # AUTHENTIFICATION JWT
    # ========================================================================

    def generate_jwt(
        self,
        wallet_id: UUID,
        user_id: UUID,
        extra_claims: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Génère un token JWT.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur
            extra_claims: Claims supplémentaires

        Returns:
            Token JWT et refresh token
        """
        try:
            now = datetime.now()
            expires_at = now + timedelta(hours=self.JWT_EXPIRY_HOURS)
            
            payload = {
                "wallet_id": str(wallet_id),
                "user_id": str(user_id),
                "iat": now.timestamp(),
                "exp": expires_at.timestamp(),
                "jti": str(uuid4())
            }
            
            if extra_claims:
                payload.update(extra_claims)
            
            token = jwt.encode(
                payload,
                self.jwt_secret,
                algorithm=self.JWT_ALGORITHM
            )
            
            refresh_token = jwt.encode(
                {
                    "wallet_id": str(wallet_id),
                    "user_id": str(user_id),
                    "iat": now.timestamp(),
                    "exp": (now + timedelta(days=self.REFRESH_TOKEN_EXPIRY_DAYS)).timestamp(),
                    "jti": str(uuid4()),
                    "refresh": True
                },
                self.jwt_secret,
                algorithm=self.JWT_ALGORITHM
            )
            
            return {
                "token": token,
                "refresh_token": refresh_token,
                "expires_at": expires_at.isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la génération du JWT: {e}")
            raise

    def verify_jwt(self, token: str) -> Dict[str, Any]:
        """
        Vérifie un token JWT.

        Args:
            token: Token JWT

        Returns:
            Payload décodé

        Raises:
            jwt.InvalidTokenError: Token invalide
        """
        try:
            # Vérification du blacklist
            if token in self._token_blacklist:
                raise jwt.InvalidTokenError("Token blacklisté")
            
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.JWT_ALGORITHM]
            )
            
            return payload

        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError("Token expiré")
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(str(e))

    def refresh_jwt(self, refresh_token: str) -> Dict[str, str]:
        """
        Rafraîchit un token JWT.

        Args:
            refresh_token: Token de rafraîchissement

        Returns:
            Nouveau token JWT
        """
        try:
            payload = self.verify_jwt(refresh_token)
            
            if not payload.get("refresh"):
                raise jwt.InvalidTokenError("Token de rafraîchissement invalide")
            
            wallet_id = UUID(payload["wallet_id"])
            user_id = UUID(payload["user_id"])
            
            return self.generate_jwt(wallet_id, user_id)

        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement du JWT: {e}")
            raise

    def revoke_jwt(self, token: str) -> None:
        """
        Révoque un token JWT.

        Args:
            token: Token à révoquer
        """
        try:
            self._token_blacklist.add(token)
            
            # Récupération du payload pour supprimer la session
            try:
                payload = self.verify_jwt(token)
                session_id = payload.get("jti")
                if session_id and session_id in self._session_cache:
                    del self._session_cache[session_id]
            except:
                pass

        except Exception as e:
            logger.error(f"Erreur lors de la révocation du JWT: {e}")

    # ========================================================================
    # GESTION DES SESSIONS
    # ========================================================================

    async def create_session(
        self,
        wallet_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        extra_claims: Optional[Dict] = None
    ) -> Session:
        """
        Crée une session utilisateur.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur
            ip_address: Adresse IP (optionnel)
            user_agent: User agent (optionnel)
            extra_claims: Claims supplémentaires

        Returns:
            Session créée
        """
        try:
            # Génération des tokens
            tokens = self.generate_jwt(wallet_id, user_id, extra_claims)
            
            session_id = uuid4()
            expires_at = datetime.fromisoformat(tokens["expires_at"])
            
            session = Session(
                session_id=session_id,
                wallet_id=wallet_id,
                user_id=user_id,
                token=tokens["token"],
                refresh_token=tokens["refresh_token"],
                expires_at=expires_at,
                created_at=datetime.now(),
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=extra_claims or {}
            )
            
            # Stockage
            self._session_cache[str(session_id)] = session
            
            if self.redis:
                key = f"security:session:{session_id}"
                await self.redis.setex(
                    key,
                    self.JWT_EXPIRY_HOURS * 3600,
                    json.dumps(session.to_dict())
                )
            
            # Enregistrement de l'événement
            await self.log_security_event(
                wallet_id=wallet_id,
                user_id=user_id,
                event_type=SecurityEventType.LOGIN,
                severity="info",
                description="Nouvelle session créée",
                metadata={
                    "session_id": str(session_id),
                    "ip_address": ip_address,
                    "user_agent": user_agent
                }
            )
            
            self._metrics["total_sessions"] += 1
            
            return session

        except Exception as e:
            logger.error(f"Erreur lors de la création de la session: {e}")
            raise

    async def get_session(
        self,
        session_id: UUID
    ) -> Optional[Session]:
        """
        Récupère une session.

        Args:
            session_id: ID de la session

        Returns:
            Session ou None
        """
        try:
            # Vérification du cache
            if str(session_id) in self._session_cache:
                return self._session_cache[str(session_id)]

            # Récupération depuis Redis
            if self.redis:
                key = f"security:session:{session_id}"
                data = await self.redis.get(key)
                if data:
                    session_dict = json.loads(data)
                    session = Session(
                        session_id=UUID(session_dict["session_id"]),
                        wallet_id=UUID(session_dict["wallet_id"]),
                        user_id=UUID(session_dict["user_id"]),
                        token=session_dict["token"],
                        refresh_token=session_dict["refresh_token"],
                        expires_at=datetime.fromisoformat(session_dict["expires_at"]),
                        created_at=datetime.fromisoformat(session_dict["created_at"]),
                        ip_address=session_dict.get("ip_address"),
                        user_agent=session_dict.get("user_agent"),
                        metadata=session_dict.get("metadata", {})
                    )
                    self._session_cache[str(session_id)] = session
                    return session

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la session: {e}")
            return None

    async def delete_session(
        self,
        session_id: UUID
    ) -> bool:
        """
        Supprime une session.

        Args:
            session_id: ID de la session

        Returns:
            True si la session a été supprimée
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            # Révocation du token
            self.revoke_jwt(session.token)
            
            # Suppression du cache
            if str(session_id) in self._session_cache:
                del self._session_cache[str(session_id)]
            
            # Suppression de Redis
            if self.redis:
                key = f"security:session:{session_id}"
                await self.redis.delete(key)
            
            # Enregistrement de l'événement
            await self.log_security_event(
                wallet_id=session.wallet_id,
                user_id=session.user_id,
                event_type=SecurityEventType.LOGOUT,
                severity="info",
                description="Session supprimée",
                metadata={"session_id": str(session_id)}
            )
            
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la session: {e}")
            return False

    # ========================================================================
    # GESTION DES CLÉS API
    # ========================================================================

    async def create_api_key(
        self,
        wallet_id: UUID,
        user_id: UUID,
        name: str,
        permissions: List[str],
        expires_in_days: Optional[int] = None
    ) -> APIKey:
        """
        Crée une clé API.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur
            name: Nom de la clé
            permissions: Permissions
            expires_in_days: Expiration en jours (optionnel)

        Returns:
            Clé API créée
        """
        try:
            key_id = uuid4()
            key = secrets.token_urlsafe(32)
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now() + timedelta(days=expires_in_days)

            api_key = APIKey(
                key_id=key_id,
                wallet_id=wallet_id,
                user_id=user_id,
                name=name,
                key=key_hash,
                permissions=permissions,
                expires_at=expires_at,
                is_active=True,
                created_at=datetime.now(),
                metadata={"key_prefix": key[:8]}
            )

            # Stockage
            self._api_key_cache[str(key_id)] = api_key
            
            if self.redis:
                key_data = api_key.to_dict()
                key_data["key"] = key  # Stockage de la clé complète
                await self.redis.setex(
                    f"security:api_key:{key_id}",
                    86400 * 30,
                    json.dumps(key_data)
                )

            # Enregistrement de l'événement
            await self.log_security_event(
                wallet_id=wallet_id,
                user_id=user_id,
                event_type=SecurityEventType.API_KEY_CREATE,
                severity="info",
                description=f"Clé API '{name}' créée",
                metadata={"key_id": str(key_id)}
            )

            self._metrics["total_api_keys"] += 1

            return api_key

        except Exception as e:
            logger.error(f"Erreur lors de la création de la clé API: {e}")
            raise

    async def verify_api_key(self, key: str) -> Optional[APIKey]:
        """
        Vérifie une clé API.

        Args:
            key: Clé API à vérifier

        Returns:
            Clé API vérifiée ou None
        """
        try:
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            
            # Recherche dans le cache
            for api_key in self._api_key_cache.values():
                if api_key.key == key_hash and api_key.is_active:
                    if api_key.expires_at and api_key.expires_at < datetime.now():
                        continue
                    return api_key

            # Recherche dans Redis
            if self.redis:
                keys = await self.redis.keys("security:api_key:*")
                for key_id in keys:
                    data = await self.redis.get(key_id)
                    if data:
                        api_key_dict = json.loads(data)
                        if api_key_dict.get("key") == key_hash:
                            api_key = APIKey(
                                key_id=UUID(api_key_dict["key_id"]),
                                wallet_id=UUID(api_key_dict["wallet_id"]),
                                user_id=UUID(api_key_dict["user_id"]),
                                name=api_key_dict["name"],
                                key=api_key_dict["key"],
                                permissions=api_key_dict["permissions"],
                                expires_at=datetime.fromisoformat(api_key_dict["expires_at"]) if api_key_dict.get("expires_at") else None,
                                is_active=api_key_dict.get("is_active", True),
                                created_at=datetime.fromisoformat(api_key_dict["created_at"]),
                                metadata=api_key_dict.get("metadata", {})
                            )
                            if api_key.is_active:
                                if api_key.expires_at and api_key.expires_at < datetime.now():
                                    continue
                                return api_key

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la vérification de la clé API: {e}")
            return None

    async def revoke_api_key(
        self,
        key_id: UUID
    ) -> bool:
        """
        Révoque une clé API.

        Args:
            key_id: ID de la clé

        Returns:
            True si la clé a été révoquée
        """
        try:
            api_key = self._api_key_cache.get(str(key_id))
            if not api_key:
                if self.redis:
                    data = await self.redis.get(f"security:api_key:{key_id}")
                    if data:
                        api_key_dict = json.loads(data)
                        api_key = APIKey(
                            key_id=UUID(api_key_dict["key_id"]),
                            wallet_id=UUID(api_key_dict["wallet_id"]),
                            user_id=UUID(api_key_dict["user_id"]),
                            name=api_key_dict["name"],
                            key=api_key_dict["key"],
                            permissions=api_key_dict["permissions"],
                            expires_at=datetime.fromisoformat(api_key_dict["expires_at"]) if api_key_dict.get("expires_at") else None,
                            is_active=api_key_dict.get("is_active", True),
                            created_at=datetime.fromisoformat(api_key_dict["created_at"]),
                            metadata=api_key_dict.get("metadata", {})
                        )
            
            if api_key:
                api_key.is_active = False
                api_key.metadata["revoked_at"] = datetime.now().isoformat()
                
                if self.redis:
                    await self.redis.setex(
                        f"security:api_key:{key_id}",
                        86400 * 30,
                        json.dumps(api_key.to_dict())
                    )

                # Enregistrement de l'événement
                await self.log_security_event(
                    wallet_id=api_key.wallet_id,
                    user_id=api_key.user_id,
                    event_type=SecurityEventType.API_KEY_REVOKE,
                    severity="info",
                    description=f"Clé API '{api_key.name}' révoquée",
                    metadata={"key_id": str(key_id)}
                )

                return True

            return False

        except Exception as e:
            logger.error(f"Erreur lors de la révocation de la clé API: {e}")
            return False

    # ========================================================================
    # DOUBLE AUTHENTIFICATION (2FA)
    # ========================================================================

    def generate_2fa_secret(self) -> Tuple[str, str]:
        """
        Génère un secret pour la 2FA.

        Returns:
            (secret, uri)
        """
        try:
            import pyotp
            
            secret = pyotp.random_base32()
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name="NEXUS Wallet",
                issuer_name="NEXUS QUANTUM"
            )
            
            return secret, provisioning_uri

        except Exception as e:
            logger.error(f"Erreur lors de la génération du secret 2FA: {e}")
            raise

    def verify_2fa_code(self, secret: str, code: str) -> bool:
        """
        Vérifie un code 2FA.

        Args:
            secret: Secret 2FA
            code: Code à vérifier

        Returns:
            True si le code est valide
        """
        try:
            import pyotp
            
            totp = pyotp.TOTP(secret)
            return totp.verify(code)

        except Exception as e:
            logger.error(f"Erreur lors de la vérification du code 2FA: {e}")
            return False

    def generate_backup_codes(self, count: int = 10) -> List[str]:
        """
        Génère des codes de sauvegarde.

        Args:
            count: Nombre de codes

        Returns:
            Liste des codes de sauvegarde
        """
        codes = []
        for _ in range(count):
            code = secrets.token_hex(4).upper()
            codes.append(f"{code[:4]}-{code[4:8]}")
        return codes

    # ========================================================================
    # ENREGISTREMENT DES ÉVÉNEMENTS DE SÉCURITÉ
    # ========================================================================

    async def log_security_event(
        self,
        wallet_id: UUID,
        user_id: UUID,
        event_type: SecurityEventType,
        severity: str,
        description: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> SecurityEvent:
        """
        Enregistre un événement de sécurité.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur
            event_type: Type d'événement
            severity: Sévérité
            description: Description
            ip_address: Adresse IP (optionnel)
            user_agent: User agent (optionnel)
            metadata: Métadonnées

        Returns:
            Événement enregistré
        """
        try:
            event = SecurityEvent(
                event_id=uuid4(),
                wallet_id=wallet_id,
                user_id=user_id,
                event_type=event_type,
                severity=severity,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.now(),
                metadata=metadata or {}
            )

            # Stockage
            if wallet_id not in self._event_cache:
                self._event_cache[wallet_id] = []
            
            self._event_cache[wallet_id].append(event)
            
            # Mise à jour des métriques
            self._metrics["total_events"] += 1
            event_type_key = event_type.value
            if event_type_key not in self._metrics["by_event_type"]:
                self._metrics["by_event_type"][event_type_key] = 0
            self._metrics["by_event_type"][event_type_key] += 1

            # Si c'est une violation de sécurité
            if event_type in [SecurityEventType.SECURITY_BREACH, SecurityEventType.SUSPICIOUS_ACTIVITY]:
                self._metrics["security_breaches"] += 1
                self._metrics["last_breach"] = datetime.now().isoformat()

            # Stockage dans Redis
            if self.redis:
                key = f"security:event:{event.event_id}"
                await self.redis.setex(
                    key,
                    86400 * 90,  # 90 jours
                    json.dumps(event.to_dict())
                )
                
                # Index par wallet
                await self.redis.sadd(
                    f"security:events:wallet:{wallet_id}",
                    str(event.event_id)
                )

            return event

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'événement: {e}")
            raise

    # ========================================================================
    # DÉTECTION DES SUSPICIONS
    # ========================================================================

    async def check_suspicious_activity(
        self,
        wallet_id: UUID,
        user_id: UUID,
        action: str,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Vérifie une activité suspecte.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur
            action: Action effectuée
            ip_address: Adresse IP (optionnel)
            metadata: Métadonnées

        Returns:
            (est_suspecte, raison)
        """
        try:
            # Vérification des échecs de connexion
            if action == "login_attempt":
                key = f"security:failed_login:{wallet_id}"
                if self.redis:
                    attempts = await self.redis.get(key)
                    attempts = int(attempts) if attempts else 0
                    
                    if attempts >= self.SUSPICIOUS_THRESHOLDS["max_login_attempts"]:
                        await self.log_security_event(
                            wallet_id=wallet_id,
                            user_id=user_id,
                            event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
                            severity="critical",
                            description="Tentatives de connexion multiples",
                            ip_address=ip_address,
                            metadata={"attempts": attempts}
                        )
                        return True, "Trop de tentatives de connexion"

            # Vérification du pays
            if ip_address:
                country = await self._get_ip_country(ip_address)
                if country in self.SUSPICIOUS_THRESHOLDS["suspicious_ip_countries"]:
                    await self.log_security_event(
                        wallet_id=wallet_id,
                        user_id=user_id,
                        event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
                        severity="warning",
                        description=f"Connexion depuis un pays suspect: {country}",
                        ip_address=ip_address,
                        metadata={"country": country}
                    )
                    return True, f"Pays suspect: {country}"

            # Vérification des transactions
            if action == "transaction":
                amount = metadata.get("amount", 0)
                wallet_config = await self.get_security_config(wallet_id, user_id)
                
                if wallet_config:
                    if amount > float(wallet_config.max_transaction_amount):
                        return True, "Montant supérieur au seuil autorisé"

            return False, None

        except Exception as e:
            logger.error(f"Erreur lors de la vérification des suspicions: {e}")
            return False, None

    async def _get_ip_country(self, ip_address: str) -> Optional[str]:
        """
        Récupère le pays d'une adresse IP.

        Args:
            ip_address: Adresse IP

        Returns:
            Code pays ou None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://ip-api.com/json/{ip_address}") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("countryCode")
            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du pays IP: {e}")
            return None

    # ========================================================================
    # CONFIGURATION DE SÉCURITÉ
    # ========================================================================

    async def get_security_config(
        self,
        wallet_id: UUID,
        user_id: UUID
    ) -> SecurityConfig:
        """
        Récupère la configuration de sécurité.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur

        Returns:
            Configuration de sécurité
        """
        try:
            # Vérification du cache
            if wallet_id in self._security_config_cache:
                return self._security_config_cache[wallet_id]

            # Récupération depuis Redis
            if self.redis:
                key = f"security:config:{wallet_id}"
                data = await self.redis.get(key)
                if data:
                    config_dict = json.loads(data)
                    config = SecurityConfig(
                        wallet_id=UUID(config_dict["wallet_id"]),
                        user_id=UUID(config_dict["user_id"]),
                        security_level=SecurityLevel(config_dict.get("security_level", "high")),
                        two_factor_enabled=config_dict.get("two_factor_enabled", False),
                        two_factor_method=TwoFactorMethod(config_dict["two_factor_method"]) if config_dict.get("two_factor_method") else None,
                        two_factor_secret=config_dict.get("two_factor_secret"),
                        backup_codes=config_dict.get("backup_codes", []),
                        whitelist_enabled=config_dict.get("whitelist_enabled", False),
                        whitelist_addresses=config_dict.get("whitelist_addresses", []),
                        ip_whitelist_enabled=config_dict.get("ip_whitelist_enabled", False),
                        ip_whitelist=config_dict.get("ip_whitelist", []),
                        session_timeout_minutes=config_dict.get("session_timeout_minutes", 60),
                        max_transaction_amount=Decimal(config_dict.get("max_transaction_amount", "10000")),
                        daily_transaction_limit=Decimal(config_dict.get("daily_transaction_limit", "50000")),
                        require_confirmation=config_dict.get("require_confirmation", True),
                        confirmation_threshold=config_dict.get("confirmation_threshold", 2),
                        suspicious_activity_alert=config_dict.get("suspicious_activity_alert", True),
                        encryption_enabled=config_dict.get("encryption_enabled", True),
                        encryption_algorithm=config_dict.get("encryption_algorithm", "AES-256-GCM"),
                        metadata=config_dict.get("metadata", {})
                    )
                    self._security_config_cache[wallet_id] = config
                    return config

            # Configuration par défaut
            config = SecurityConfig(
                wallet_id=wallet_id,
                user_id=user_id
            )
            self._security_config_cache[wallet_id] = config
            return config

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la configuration de sécurité: {e}")
            return SecurityConfig(wallet_id=wallet_id, user_id=user_id)

    async def update_security_config(
        self,
        config: SecurityConfig
    ) -> bool:
        """
        Met à jour la configuration de sécurité.

        Args:
            config: Nouvelle configuration

        Returns:
            True si la mise à jour a réussi
        """
        try:
            config.updated_at = datetime.now()
            
            # Mise en cache
            self._security_config_cache[config.wallet_id] = config
            
            # Sauvegarde dans Redis
            if self.redis:
                key = f"security:config:{config.wallet_id}"
                await self.redis.setex(
                    key,
                    86400 * 30,
                    json.dumps(config.to_dict())
                )

            # Enregistrement de l'événement
            await self.log_security_event(
                wallet_id=config.wallet_id,
                user_id=config.user_id,
                event_type=SecurityEventType.CONFIG_CHANGE,
                severity="info",
                description="Configuration de sécurité mise à jour",
                metadata={"changes": config.to_dict()}
            )

            return True

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la configuration de sécurité: {e}")
            return False

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_security_events(
        self,
        wallet_id: UUID,
        event_type: Optional[SecurityEventType] = None,
        severity: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SecurityEvent]:
        """
        Récupère les événements de sécurité.

        Args:
            wallet_id: ID du wallet
            event_type: Filtrer par type
            severity: Filtrer par sévérité
            from_date: Date de début
            to_date: Date de fin
            limit: Nombre d'événements
            offset: Décalage

        Returns:
            Liste des événements
        """
        try:
            events = self._event_cache.get(wallet_id, [])
            
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            
            if severity:
                events = [e for e in events if e.severity == severity]
            
            if from_date:
                events = [e for e in events if e.timestamp >= from_date]
            
            if to_date:
                events = [e for e in events if e.timestamp <= to_date]
            
            events.sort(key=lambda x: x.timestamp, reverse=True)
            
            return events[offset:offset + limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des événements de sécurité: {e}")
            return []

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_events": self._metrics["total_events"],
                "total_sessions": self._metrics["total_sessions"],
                "total_api_keys": self._metrics["total_api_keys"],
                "security_breaches": self._metrics["security_breaches"],
                "suspicious_activities": self._metrics["suspicious_activities"],
                "last_breach": self._metrics["last_breach"],
                "cached_configs": len(self._security_config_cache),
                "active_sessions": len(self._session_cache),
                "active_api_keys": len(self._api_key_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de WalletSecurity...")
        self._security_config_cache.clear()
        self._session_cache.clear()
        self._api_key_cache.clear()
        self._event_cache.clear()
        self._token_blacklist.clear()
        logger.info("WalletSecurity fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_security(
    redis_url: str = "redis://localhost:6379/0",
    jwt_secret: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> WalletSecurity:
    """
    Crée une instance du service de sécurité.

    Args:
        redis_url: URL de connexion Redis
        jwt_secret: Secret JWT (optionnel)
        api_keys: Clés API

    Returns:
        Instance du service
    """
    import redis.asyncio as redis
    import os
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return WalletSecurity(
        redis_client=redis_client,
        jwt_secret=jwt_secret,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "SecurityLevel",
    "SecurityEventType",
    "TwoFactorMethod",
    "SecurityConfig",
    "SecurityEvent",
    "APIKey",
    "Session",
    "WalletSecurity",
    "create_wallet_security"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du service de sécurité."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET SECURITY MODULE")
    print("=" * 60)

    # Création du service
    security = create_wallet_security(
        jwt_secret=secrets.token_hex(32)
    )

    # Création d'un wallet exemple
    from .ethereum_wallet import create_ethereum_wallet
    from uuid import UUID
    
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    wallet = create_ethereum_wallet(
        user_id=user_id,
        name="Security Wallet"
    )
    
    await wallet.initialize()

    print(f"\n✅ Wallet créé:")
    print(f"   Adresse: {wallet.config.address}")

    # Configuration de sécurité
    config = SecurityConfig(
        wallet_id=wallet.config.wallet_id,
        user_id=user_id,
        security_level=SecurityLevel.HIGH,
        max_transaction_amount=Decimal("5000"),
        require_confirmation=True
    )
    
    await security.update_security_config(config)
    print(f"\n🔒 Configuration de sécurité mise à jour")

    # Création d'une session
    session = await security.create_session(
        wallet_id=wallet.config.wallet_id,
        user_id=user_id,
        ip_address="127.0.0.1",
        user_agent="NEXUS-TEST"
    )
    print(f"\n🔐 Session créée:")
    print(f"   ID: {session.session_id}")
    print(f"   Token: {session.token[:20]}...")

    # Vérification JWT
    try:
        payload = security.verify_jwt(session.token)
        print(f"\n✅ JWT valide: {payload}")
    except Exception as e:
        print(f"\n❌ JWT invalide: {e}")

    # Création d'une clé API
    api_key = await security.create_api_key(
        wallet_id=wallet.config.wallet_id,
        user_id=user_id,
        name="Test API Key",
        permissions=["read", "write"],
        expires_in_days=30
    )
    print(f"\n🔑 Clé API créée:")
    print(f"   ID: {api_key.key_id}")
    print(f"   Nom: {api_key.name}")
    print(f"   Permissions: {api_key.permissions}")

    # Vérification 2FA
    secret, uri = security.generate_2fa_secret()
    print(f"\n📱 Secret 2FA généré:")
    print(f"   Secret: {secret}")
    print(f"   URI: {uri}")

    # Enregistrement d'un événement de sécurité
    event = await security.log_security_event(
        wallet_id=wallet.config.wallet_id,
        user_id=user_id,
        event_type=SecurityEventType.LOGIN,
        severity="info",
        description="Login réussi",
        ip_address="127.0.0.1"
    )
    print(f"\n📋 Événement enregistré:")
    print(f"   ID: {event.event_id}")
    print(f"   Type: {event.event_type.value}")
    print(f"   Description: {event.description}")

    # Récupération des événements
    events = await security.get_security_events(wallet.config.wallet_id)
    print(f"\n📊 Événements de sécurité: {len(events)}")

    # Santé du service
    health = await security.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Événements: {health['total_events']}")
    print(f"   Sessions: {health['total_sessions']}")
    print(f"   Clés API: {health['total_api_keys']}")

    # Fermeture
    await security.close()
    await wallet.close()

    print("\n" + "=" * 60)
    print("WalletSecurity NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import os
    import secrets
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
