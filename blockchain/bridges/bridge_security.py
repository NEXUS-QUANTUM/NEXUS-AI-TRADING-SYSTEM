
# blockchain/bridges/bridge_security.py
"""
NEXUS AI TRADING SYSTEM - Bridge Security Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import hashlib
import hmac
import json
import time
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

try:
    from eth_account import Account
    from eth_account.signers.local import LocalAccount
    ETH_ACCOUNT_AVAILABLE = True
except ImportError:
    ETH_ACCOUNT_AVAILABLE = False

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Niveaux de sécurité"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BridgeSecurityConfig:
    """Configuration de sécurité du bridge"""
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    enable_encryption: bool = True
    enable_signing: bool = True
    enable_rate_limiting: bool = True
    enable_ip_whitelist: bool = False
    enable_2fa: bool = False
    max_transaction_value: float = 100000.0
    min_balance: float = 0.01
    rate_limit: int = 100  # requêtes par minute
    rate_limit_window: int = 60  # secondes
    whitelisted_ips: List[str] = field(default_factory=list)
    blacklisted_addresses: List[str] = field(default_factory=list)
    encryption_key: Optional[str] = None
    signature_algorithm: str = "HS256"
    session_timeout: int = 3600  # secondes

    def to_dict(self) -> Dict[str, Any]:
        return {
            'security_level': self.security_level.value,
            'enable_encryption': self.enable_encryption,
            'enable_signing': self.enable_signing,
            'enable_rate_limiting': self.enable_rate_limiting,
            'enable_ip_whitelist': self.enable_ip_whitelist,
            'enable_2fa': self.enable_2fa,
            'max_transaction_value': self.max_transaction_value,
            'min_balance': self.min_balance,
            'rate_limit': self.rate_limit,
            'rate_limit_window': self.rate_limit_window,
            'whitelisted_ips': self.whitelisted_ips,
            'blacklisted_addresses': self.blacklisted_addresses,
            'signature_algorithm': self.signature_algorithm,
            'session_timeout': self.session_timeout,
        }


@dataclass
class SecurityContext:
    """Contexte de sécurité"""
    user_id: str
    ip_address: str
    session_id: str
    timestamp: datetime
    permissions: List[str]
    security_level: SecurityLevel

    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'permissions': self.permissions,
            'security_level': self.security_level.value,
        }


class BridgeSecurity:
    """
    Sécurité pour les bridges blockchain.

    Features:
    - Chiffrement
    - Signature
    - Rate limiting
    - Whitelist IP
    - 2FA
    - Session management

    Example:
        ```python
        config = BridgeSecurityConfig(
            security_level=SecurityLevel.HIGH,
            enable_encryption=True,
            enable_signing=True
        )
        security = BridgeSecurity(config)

        # Vérification de sécurité
        if security.check_security(context):
            # Opération sécurisée
            pass
        ```
    """

    def __init__(self, config: Optional[BridgeSecurityConfig] = None):
        if not ETH_ACCOUNT_AVAILABLE:
            raise ImportError("eth_account n'est pas installé")

        self.config = config or BridgeSecurityConfig()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._rate_limits: Dict[str, List[float]] = {}

        # Initialisation du chiffrement
        self._init_encryption()

        logger.info(f"BridgeSecurity initialisé (niveau: {self.config.security_level.value})")

    def _init_encryption(self):
        """Initialise le chiffrement"""
        if not CRYPTOGRAPHY_AVAILABLE:
            logger.warning("Cryptographie non disponible")

        if self.config.encryption_key:
            self.cipher = Fernet(self.config.encryption_key.encode())
        else:
            # Génération d'une clé
            key = Fernet.generate_key()
            self.cipher = Fernet(key)
            logger.warning("Clé de chiffrement générée automatiquement")

    def check_security(self, context: SecurityContext) -> bool:
        """
        Vérifie les contraintes de sécurité.

        Args:
            context: Contexte de sécurité

        Returns:
            bool: True si sécurisé
        """
        checks = []

        # Niveau de sécurité
        if self._check_security_level(context):
            checks.append(True)

        # Rate limiting
        if self.config.enable_rate_limiting:
            checks.append(self._check_rate_limit(context))

        # IP Whitelist
        if self.config.enable_ip_whitelist:
            checks.append(self._check_ip_whitelist(context))

        # Session
        checks.append(self._check_session(context))

        return all(checks)

    def _check_security_level(self, context: SecurityContext) -> bool:
        """
        Vérifie le niveau de sécurité.

        Args:
            context: Contexte de sécurité

        Returns:
            bool: True si valide
        """
        required_level = context.security_level
        current_level = self.config.security_level

        levels = {
            SecurityLevel.LOW: 0,
            SecurityLevel.MEDIUM: 1,
            SecurityLevel.HIGH: 2,
            SecurityLevel.CRITICAL: 3,
        }

        return levels.get(current_level, 1) >= levels.get(required_level, 1)

    def _check_rate_limit(self, context: SecurityContext) -> bool:
        """
        Vérifie le rate limiting.

        Args:
            context: Contexte de sécurité

        Returns:
            bool: True si OK
        """
        key = f"{context.user_id}:{context.ip_address}"
        now = time.time()

        if key not in self._rate_limits:
            self._rate_limits[key] = []

        # Nettoyage des entrées anciennes
        self._rate_limits[key] = [
            ts for ts in self._rate_limits[key]
            if now - ts < self.config.rate_limit_window
        ]

        # Vérification de la limite
        if len(self._rate_limits[key]) >= self.config.rate_limit:
            logger.warning(f"Rate limit dépassé pour {key}")
            return False

        self._rate_limits[key].append(now)
        return True

    def _check_ip_whitelist(self, context: SecurityContext) -> bool:
        """
        Vérifie l'IP dans la whitelist.

        Args:
            context: Contexte de sécurité

        Returns:
            bool: True si autorisé
        """
        if not self.config.whitelisted_ips:
            return True

        return context.ip_address in self.config.whitelisted_ips

    def _check_session(self, context: SecurityContext) -> bool:
        """
        Vérifie la session.

        Args:
            context: Contexte de sécurité

        Returns:
            bool: True si valide
        """
        if context.session_id not in self._sessions:
            logger.warning(f"Session invalide: {context.session_id}")
            return False

        session = self._sessions[context.session_id]
        session_time = session.get('timestamp', datetime.now())

        if (datetime.now() - session_time).seconds > self.config.session_timeout:
            logger.warning(f"Session expirée: {context.session_id}")
            return False

        return True

    def create_session(
        self,
        user_id: str,
        ip_address: str,
        permissions: List[str] = None
    ) -> str:
        """
        Crée une session sécurisée.

        Args:
            user_id: ID de l'utilisateur
            ip_address: Adresse IP
            permissions: Permissions

        Returns:
            str: ID de session
        """
        import uuid
        session_id = str(uuid.uuid4())

        context = SecurityContext(
            user_id=user_id,
            ip_address=ip_address,
            session_id=session_id,
            timestamp=datetime.now(),
            permissions=permissions or [],
            security_level=self.config.security_level,
        )

        self._sessions[session_id] = {
            'context': context,
            'timestamp': datetime.now(),
            'permissions': permissions or [],
        }

        logger.info(f"Session créée: {session_id}")
        return session_id

    def end_session(self, session_id: str) -> bool:
        """
        Termine une session.

        Args:
            session_id: ID de session

        Returns:
            bool: True si terminée
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Session terminée: {session_id}")
            return True

        return False

    def encrypt_data(self, data: Any) -> bytes:
        """
        Chiffre des données.

        Args:
            data: Données à chiffrer

        Returns:
            bytes: Données chiffrées
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            return json.dumps(data).encode()

        return self.cipher.encrypt(json.dumps(data).encode())

    def decrypt_data(self, encrypted_data: bytes) -> Any:
        """
        Déchiffre des données.

        Args:
            encrypted_data: Données chiffrées

        Returns:
            Any: Données déchiffrées
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            return json.loads(encrypted_data)

        decrypted = self.cipher.decrypt(encrypted_data)
        return json.loads(decrypted)

    def sign_transaction(self, transaction: Dict[str, Any], private_key: str) -> str:
        """
        Signe une transaction.

        Args:
            transaction: Transaction à signer
            private_key: Clé privée

        Returns:
            str: Signature
        """
        if not self.config.enable_signing:
            return ""

        # Hash de la transaction
        tx_hash = hashlib.sha256(json.dumps(transaction, sort_keys=True).encode()).hexdigest()

        # Signature
        account = Account.from_key(private_key)
        signed = account.signHash(web3.Web3.soliditySha3(['string'], [tx_hash]))

        return signed.signature.hex()

    def verify_signature(self, transaction: Dict[str, Any], signature: str) -> bool:
        """
        Vérifie une signature.

        Args:
            transaction: Transaction
            signature: Signature

        Returns:
            bool: True si valide
        """
        if not self.config.enable_signing:
            return True

        # Hash de la transaction
        tx_hash = hashlib.sha256(json.dumps(transaction, sort_keys=True).encode()).hexdigest()

        # Vérification
        try:
            account = Account.recoverHash(
                Web3.soliditySha3(['string'], [tx_hash]),
                signature=signature
            )
            return account == transaction.get('from')
        except Exception as e:
            logger.error(f"Erreur de vérification: {e}")
            return False

    def get_security_status(self) -> Dict[str, Any]:
        """
        Retourne le statut de sécurité.

        Returns:
            Dict[str, Any]: Statut
        """
        return {
            'security_level': self.config.security_level.value,
            'encryption_enabled': self.config.enable_encryption,
            'signing_enabled': self.config.enable_signing,
            'rate_limiting_enabled': self.config.enable_rate_limiting,
            'ip_whitelist_enabled': self.config.enable_ip_whitelist,
            '2fa_enabled': self.config.enable_2fa,
            'active_sessions': len(self._sessions),
            'max_transaction_value': self.config.max_transaction_value,
            'min_balance': self.config.min_balance,
            'rate_limit': self.config.rate_limit,
        }


def create_bridge_security(
    security_level: str = "medium",
    enable_encryption: bool = True,
    **kwargs
) -> BridgeSecurity:
    """
    Factory pour créer une sécurité de bridge.

    Args:
        security_level: Niveau de sécurité
        enable_encryption: Activer le chiffrement
        **kwargs: Arguments supplémentaires

    Returns:
        BridgeSecurity: Sécurité
    """
    level_map = {
        'low': SecurityLevel.LOW,
        'medium': SecurityLevel.MEDIUM,
        'high': SecurityLevel.HIGH,
        'critical': SecurityLevel.CRITICAL,
    }

    config = BridgeSecurityConfig(
        security_level=level_map.get(security_level.lower(), SecurityLevel.MEDIUM),
        enable_encryption=enable_encryption,
        **kwargs
    )
    return BridgeSecurity(config)


__all__ = [
    'BridgeSecurity',
    'BridgeSecurityConfig',
    'SecurityContext',
    'SecurityLevel',
    'create_bridge_security',
]
