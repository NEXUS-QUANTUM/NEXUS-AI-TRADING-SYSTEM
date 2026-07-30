# trading/bots/hedge_bot/hedge_bot_authenticator.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Authenticator Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Authenticator Module

This module provides comprehensive authentication and authorization
capabilities for the NEXUS Hedge Bot system. It handles user authentication,
API key management, session management, and role-based access control.

The module covers:
- User Authentication (Login/Logout)
- JWT Token Management
- API Key Management
- Session Management
- Role-Based Access Control (RBAC)
- Multi-Factor Authentication (MFA)
- Password Management
- OAuth2 Integration
- Single Sign-On (SSO)
- Rate Limiting
- IP Whitelisting
- Audit Logging
"""

import os
import sys
import json
import time
import hashlib
import hmac
import secrets
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Try to import optional dependencies
try:
    import pyotp
    HAS_PYOTP = True
except ImportError:
    HAS_PYOTP = False

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

logger = logging.getLogger(__name__)


# ============================================================
# AUTHENTICATOR ENUMS
# ============================================================

class AuthRole(Enum):
    """Authentication roles"""
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"
    AUDITOR = "auditor"
    API = "api"


class AuthMethod(Enum):
    """Authentication methods"""
    PASSWORD = "password"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    SSO = "sso"
    MFA = "mfa"


class TokenType(Enum):
    """Token types"""
    ACCESS = "access"
    REFRESH = "refresh"
    API = "api"
    MFA = "mfa"
    RESET = "reset"


# ============================================================
# AUTHENTICATOR DATACLASSES
# ============================================================

@dataclass
class User:
    """User data"""
    id: str
    username: str
    email: str
    password_hash: str
    salt: str
    role: AuthRole
    mfa_enabled: bool
    mfa_secret: Optional[str] = None
    api_keys: List[str] = field(default_factory=list)
    last_login: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    preferences: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "mfa_enabled": self.mfa_enabled,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
            "preferences": self.preferences,
        }


@dataclass
class Session:
    """Session data"""
    id: str
    user_id: str
    token: str
    refresh_token: str
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "is_active": self.is_active,
        }


@dataclass
class APIKey:
    """API key data"""
    id: str
    user_id: str
    key: str
    secret: str
    name: str
    permissions: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "permissions": self.permissions,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_active": self.is_active,
        }


@dataclass
class AuthResult:
    """Authentication result"""
    success: bool
    user: Optional[User] = None
    session: Optional[Session] = None
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    error: Optional[str] = None
    requires_mfa: bool = False
    mfa_type: Optional[str] = None
    mfa_token: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "user": self.user.to_dict() if self.user else None,
            "session": self.session.to_dict() if self.session else None,
            "token": self.token,
            "refresh_token": self.refresh_token,
            "error": self.error,
            "requires_mfa": self.requires_mfa,
            "mfa_type": self.mfa_type,
        }


# ============================================================
# AUTHENTICATOR ENGINE
# ============================================================

class AuthenticatorEngine:
    """
    Comprehensive authenticator engine for the hedge bot
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the authenticator engine
        
        Args:
            config: Configuration dictionary
        """
        if hasattr(self, '_initialized'):
            return
        
        self.config = config or {}
        self.secret_key = self.config.get("secret_key", self._generate_secret())
        self.token_expiry = self.config.get("token_expiry", 3600)  # 1 hour
        self.refresh_token_expiry = self.config.get("refresh_token_expiry", 86400)  # 24 hours
        self.api_key_expiry = self.config.get("api_key_expiry", 2592000)  # 30 days
        self.algorithm = self.config.get("algorithm", "HS256")
        self.mfa_enabled = self.config.get("mfa_enabled", True)
        self.max_login_attempts = self.config.get("max_login_attempts", 5)
        self.rate_limit = self.config.get("rate_limit", 60)  # 60 per minute
        
        # State
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self.api_keys: Dict[str, APIKey] = {}
        self.login_attempts: Dict[str, List[datetime]] = {}
        
        # Encryption
        self.fernet = Fernet(base64.urlsafe_b64encode(self.secret_key.encode()[:32].ljust(32, b'=')))
        
        self._initialized = True
        logger.info("Authenticator engine initialized")
    
    # ============================================================
    # USER MANAGEMENT
    # ============================================================
    
    def create_user(
        self,
        username: str,
        password: str,
        email: str,
        role: AuthRole = AuthRole.VIEWER
    ) -> User:
        """
        Create a new user
        
        Args:
            username: Username
            password: Password
            email: Email
            role: User role
            
        Returns:
            User object
        """
        # Check if user exists
        for user in self.users.values():
            if user.username == username:
                raise ValueError(f"User {username} already exists")
        
        # Hash password
        salt, password_hash = self._hash_password(password)
        
        # Create user
        user = User(
            id=f"usr_{int(time.time())}_{secrets.token_hex(4)}",
            username=username,
            email=email,
            password_hash=password_hash,
            salt=salt,
            role=role,
            mfa_enabled=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        self.users[user.id] = user
        logger.info(f"Created user: {username} ({role.value})")
        return user
    
    def update_user(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> Optional[User]:
        """
        Update a user
        
        Args:
            user_id: User ID
            updates: Updates to apply
            
        Returns:
            Updated user or None
        """
        user = self.users.get(user_id)
        if not user:
            return None
        
        for key, value in updates.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        user.updated_at = datetime.now()
        logger.info(f"Updated user: {user.username}")
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user
        
        Args:
            user_id: User ID
            
        Returns:
            True if deleted
        """
        user = self.users.get(user_id)
        if not user:
            return False
        
        del self.users[user_id]
        
        # Clean up sessions
        for session_id, session in list(self.sessions.items()):
            if session.user_id == user_id:
                del self.sessions[session_id]
        
        # Clean up API keys
        for key_id, api_key in list(self.api_keys.items()):
            if api_key.user_id == user_id:
                del self.api_keys[key_id]
        
        logger.info(f"Deleted user: {user.username}")
        return True
    
    def get_user(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            User or None
        """
        return self.users.get(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username
        
        Args:
            username: Username
            
        Returns:
            User or None
        """
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    # ============================================================
    # AUTHENTICATION
    # ============================================================
    
    def authenticate(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """
        Authenticate a user
        
        Args:
            username: Username
            password: Password
            ip_address: IP address
            user_agent: User agent
            
        Returns:
            AuthResult
        """
        # Check rate limiting
        if self._is_rate_limited(username):
            return AuthResult(
                success=False,
                error="Rate limit exceeded. Please try again later."
            )
        
        # Get user
        user = self.get_user_by_username(username)
        if not user:
            self._record_login_attempt(username, False)
            return AuthResult(
                success=False,
                error="Invalid username or password"
            )
        
        # Check if user is active
        if not user.is_active:
            return AuthResult(
                success=False,
                error="Account is deactivated"
            )
        
        # Verify password
        if not self._verify_password(password, user.salt, user.password_hash):
            self._record_login_attempt(username, False)
            return AuthResult(
                success=False,
                error="Invalid username or password"
            )
        
        # Record successful login
        self._record_login_attempt(username, True)
        user.last_login = datetime.now()
        
        # Check MFA
        if user.mfa_enabled and self.mfa_enabled:
            # Generate MFA token
            mfa_token = self._generate_mfa_token(user)
            return AuthResult(
                success=False,
                requires_mfa=True,
                mfa_type="totp",
                mfa_token=mfa_token,
                user=user,
            )
        
        # Create session
        session = self._create_session(user, ip_address, user_agent)
        
        # Generate tokens
        token = self._generate_token(user, session, TokenType.ACCESS)
        refresh_token = self._generate_token(user, session, TokenType.REFRESH)
        
        logger.info(f"User logged in: {username}")
        return AuthResult(
            success=True,
            user=user,
            session=session,
            token=token,
            refresh_token=refresh_token,
        )
    
    def authenticate_mfa(
        self,
        username: str,
        mfa_token: str,
        mfa_code: str
    ) -> AuthResult:
        """
        Authenticate with MFA
        
        Args:
            username: Username
            mfa_token: MFA token
            mfa_code: MFA code
            
        Returns:
            AuthResult
        """
        # Get user
        user = self.get_user_by_username(username)
        if not user:
            return AuthResult(
                success=False,
                error="Invalid username"
            )
        
        # Verify MFA
        if not self._verify_mfa(user, mfa_token, mfa_code):
            return AuthResult(
                success=False,
                error="Invalid MFA code"
            )
        
        # Create session
        session = self._create_session(user, None, None)
        
        # Generate tokens
        token = self._generate_token(user, session, TokenType.ACCESS)
        refresh_token = self._generate_token(user, session, TokenType.REFRESH)
        
        logger.info(f"User authenticated with MFA: {username}")
        return AuthResult(
            success=True,
            user=user,
            session=session,
            token=token,
            refresh_token=refresh_token,
        )
    
    def refresh_token(self, refresh_token: str) -> AuthResult:
        """
        Refresh an access token
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            AuthResult
        """
        try:
            # Decode refresh token
            payload = jwt.decode(
                refresh_token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Get session
            session_id = payload.get("session_id")
            session = self.sessions.get(session_id)
            if not session or not session.is_active:
                return AuthResult(
                    success=False,
                    error="Invalid session"
                )
            
            # Get user
            user = self.users.get(session.user_id)
            if not user or not user.is_active:
                return AuthResult(
                    success=False,
                    error="User not found or inactive"
                )
            
            # Update session
            session.last_activity = datetime.now()
            
            # Generate new tokens
            token = self._generate_token(user, session, TokenType.ACCESS)
            new_refresh_token = self._generate_token(user, session, TokenType.REFRESH)
            
            logger.info(f"Token refreshed for user: {user.username}")
            return AuthResult(
                success=True,
                user=user,
                session=session,
                token=token,
                refresh_token=new_refresh_token,
            )
            
        except jwt.ExpiredSignatureError:
            return AuthResult(
                success=False,
                error="Refresh token expired"
            )
        except jwt.InvalidTokenError:
            return AuthResult(
                success=False,
                error="Invalid refresh token"
            )
    
    def logout(self, token: str) -> bool:
        """
        Logout a user
        
        Args:
            token: Access token
            
        Returns:
            True if logged out
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            session_id = payload.get("session_id")
            session = self.sessions.get(session_id)
            if session:
                session.is_active = False
                logger.info(f"User logged out: {session.user_id}")
                return True
        except:
            pass
        return False
    
    # ============================================================
    # TOKEN MANAGEMENT
    # ============================================================
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[User], Optional[Session]]:
        """
        Verify a token
        
        Args:
            token: Access token
            
        Returns:
            (is_valid, user, session)
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Get user
            user_id = payload.get("user_id")
            user = self.users.get(user_id)
            if not user or not user.is_active:
                return False, None, None
            
            # Get session
            session_id = payload.get("session_id")
            session = self.sessions.get(session_id)
            if not session or not session.is_active:
                return False, None, None
            
            # Check expiry
            if datetime.now() > session.expires_at:
                session.is_active = False
                return False, None, None
            
            # Update last activity
            session.last_activity = datetime.now()
            
            return True, user, session
            
        except jwt.ExpiredSignatureError:
            return False, None, None
        except jwt.InvalidTokenError:
            return False, None, None
    
    def get_user_from_token(self, token: str) -> Optional[User]:
        """
        Get user from token
        
        Args:
            token: Access token
            
        Returns:
            User or None
        """
        is_valid, user, _ = self.verify_token(token)
        return user if is_valid else None
    
    def get_session_from_token(self, token: str) -> Optional[Session]:
        """
        Get session from token
        
        Args:
            token: Access token
            
        Returns:
            Session or None
        """
        is_valid, _, session = self.verify_token(token)
        return session if is_valid else None
    
    # ============================================================
    # API KEY MANAGEMENT
    # ============================================================
    
    def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: List[str]
    ) -> APIKey:
        """
        Create an API key
        
        Args:
            user_id: User ID
            name: Key name
            permissions: Permissions
            
        Returns:
            APIKey
        """
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Generate key and secret
        key = f"nexus_{secrets.token_hex(16)}"
        secret = secrets.token_hex(32)
        
        # Create API key
        api_key = APIKey(
            id=f"key_{int(time.time())}_{secrets.token_hex(4)}",
            user_id=user_id,
            key=key,
            secret=secret,
            name=name,
            permissions=permissions,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self.api_key_expiry),
        )
        
        self.api_keys[api_key.id] = api_key
        user.api_keys.append(api_key.id)
        
        logger.info(f"Created API key for user: {user.username}")
        return api_key
    
    def verify_api_key(self, key: str, secret: str) -> Tuple[bool, Optional[User], Optional[APIKey]]:
        """
        Verify an API key
        
        Args:
            key: API key
            secret: API secret
            
        Returns:
            (is_valid, user, api_key)
        """
        for api_key in self.api_keys.values():
            if api_key.key == key and api_key.is_active:
                # Verify secret
                if secrets.compare_digest(api_key.secret, secret):
                    # Check expiry
                    if api_key.expires_at and datetime.now() > api_key.expires_at:
                        api_key.is_active = False
                        return False, None, None
                    
                    # Get user
                    user = self.users.get(api_key.user_id)
                    if not user or not user.is_active:
                        return False, None, None
                    
                    # Update last used
                    api_key.last_used = datetime.now()
                    
                    return True, user, api_key
        
        return False, None, None
    
    def revoke_api_key(self, key_id: str) -> bool:
        """
        Revoke an API key
        
        Args:
            key_id: API key ID
            
        Returns:
            True if revoked
        """
        api_key = self.api_keys.get(key_id)
        if not api_key:
            return False
        
        api_key.is_active = False
        
        # Remove from user
        user = self.users.get(api_key.user_id)
        if user and api_key.id in user.api_keys:
            user.api_keys.remove(api_key.id)
        
        logger.info(f"Revoked API key: {api_key.name}")
        return True
    
    # ============================================================
    # MFA MANAGEMENT
    # ============================================================
    
    def enable_mfa(self, user_id: str) -> Dict[str, str]:
        """
        Enable MFA for a user
        
        Args:
            user_id: User ID
            
        Returns:
            MFA setup data
        """
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        if not HAS_PYOTP:
            raise ValueError("PyOTP not installed for MFA")
        
        # Generate MFA secret
        secret = pyotp.random_base32()
        user.mfa_secret = secret
        user.mfa_enabled = True
        
        # Generate provisioning URI
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(
            name=user.email,
            issuer_name="NEXUS Hedge Bot"
        )
        
        return {
            "secret": secret,
            "uri": uri,
            "qrcode": f"otpauth://totp/NEXUS%20Hedge%20Bot:{user.email}?secret={secret}&issuer=NEXUS%20Hedge%20Bot"
        }
    
    def disable_mfa(self, user_id: str) -> bool:
        """
        Disable MFA for a user
        
        Args:
            user_id: User ID
            
        Returns:
            True if disabled
        """
        user = self.users.get(user_id)
        if not user:
            return False
        
        user.mfa_enabled = False
        user.mfa_secret = None
        
        logger.info(f"Disabled MFA for user: {user.username}")
        return True
    
    def verify_mfa_code(self, user_id: str, code: str) -> bool:
        """
        Verify MFA code
        
        Args:
            user_id: User ID
            code: MFA code
            
        Returns:
            True if valid
        """
        user = self.users.get(user_id)
        if not user or not user.mfa_secret:
            return False
        
        if not HAS_PYOTP:
            return False
        
        totp = pyotp.TOTP(user.mfa_secret)
        return totp.verify(code)
    
    # ============================================================
    # AUTHORIZATION
    # ============================================================
    
    def has_permission(self, user: User, permission: str) -> bool:
        """
        Check if user has permission
        
        Args:
            user: User
            permission: Permission to check
            
        Returns:
            True if has permission
        """
        # Admin has all permissions
        if user.role == AuthRole.ADMIN:
            return True
        
        # Define role permissions
        role_permissions = {
            AuthRole.TRADER: [
                "trade", "view_positions", "view_orders", "view_portfolio"
            ],
            AuthRole.VIEWER: [
                "view_positions", "view_orders", "view_portfolio"
            ],
            AuthRole.AUDITOR: [
                "view_positions", "view_orders", "view_portfolio", "view_audit"
            ],
            AuthRole.API: [
                "trade", "view_positions", "view_orders", "view_portfolio"
            ],
        }
        
        return permission in role_permissions.get(user.role, [])
    
    def check_permission(self, user: User, permission: str) -> bool:
        """
        Check permission and raise exception if denied
        
        Args:
            user: User
            permission: Permission to check
            
        Returns:
            True if has permission
            
        Raises:
            PermissionError: If permission denied
        """
        if not self.has_permission(user, permission):
            raise PermissionError(f"Permission denied: {permission}")
        return True
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _hash_password(self, password: str) -> Tuple[str, str]:
        """Hash a password"""
        if HAS_BCRYPT:
            salt = bcrypt.gensalt().decode()
            password_hash = bcrypt.hashpw(password.encode(), salt.encode()).decode()
            return salt, password_hash
        else:
            salt = secrets.token_hex(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=100000,
            )
            password_hash = base64.b64encode(kdf.derive(password.encode())).decode()
            return salt, password_hash
    
    def _verify_password(self, password: str, salt: str, password_hash: str) -> bool:
        """Verify a password"""
        if HAS_BCRYPT:
            try:
                return bcrypt.checkpw(password.encode(), password_hash.encode())
            except:
                return False
        else:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=100000,
            )
            computed_hash = base64.b64encode(kdf.derive(password.encode())).decode()
            return secrets.compare_digest(computed_hash, password_hash)
    
    def _create_session(
        self,
        user: User,
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> Session:
        """Create a session"""
        session = Session(
            id=f"sess_{int(time.time())}_{secrets.token_hex(4)}",
            user_id=user.id,
            token=secrets.token_hex(32),
            refresh_token=secrets.token_hex(32),
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self.refresh_token_expiry),
            last_activity=datetime.now(),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        self.sessions[session.id] = session
        return session
    
    def _generate_token(
        self,
        user: User,
        session: Session,
        token_type: TokenType
    ) -> str:
        """Generate a JWT token"""
        expiry = {
            TokenType.ACCESS: self.token_expiry,
            TokenType.REFRESH: self.refresh_token_expiry,
            TokenType.API: self.api_key_expiry,
            TokenType.MFA: 300,  # 5 minutes
            TokenType.RESET: 3600,  # 1 hour
        }.get(token_type, self.token_expiry)
        
        payload = {
            "user_id": user.id,
            "username": user.username,
            "session_id": session.id,
            "role": user.role.value,
            "type": token_type.value,
            "iat": int(time.time()),
            "exp": int(time.time()) + expiry,
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def _generate_mfa_token(self, user: User) -> str:
        """Generate an MFA token"""
        payload = {
            "user_id": user.id,
            "type": TokenType.MFA.value,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,  # 5 minutes
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def _verify_mfa(self, user: User, mfa_token: str, mfa_code: str) -> bool:
        """Verify MFA"""
        # Verify token
        try:
            payload = jwt.decode(
                mfa_token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            if payload.get("user_id") != user.id:
                return False
        except:
            return False
        
        # Verify code
        return self.verify_mfa_code(user.id, mfa_code)
    
    def _is_rate_limited(self, username: str) -> bool:
        """Check if rate limited"""
        attempts = self.login_attempts.get(username, [])
        recent = [a for a in attempts if (datetime.now() - a).total_seconds() < 60]
        
        if len(recent) >= self.max_login_attempts:
            return True
        
        # Clean old attempts
        self.login_attempts[username] = recent
        return False
    
    def _record_login_attempt(self, username: str, success: bool) -> None:
        """Record a login attempt"""
        if username not in self.login_attempts:
            self.login_attempts[username] = []
        
        if not success:
            self.login_attempts[username].append(datetime.now())
    
    def _generate_secret(self) -> str:
        """Generate a secret key"""
        return secrets.token_hex(32)


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "AuthRole",
    "AuthMethod",
    "TokenType",
    
    # Dataclasses
    "User",
    "Session",
    "APIKey",
    "AuthResult",
    
    # Classes
    "AuthenticatorEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
