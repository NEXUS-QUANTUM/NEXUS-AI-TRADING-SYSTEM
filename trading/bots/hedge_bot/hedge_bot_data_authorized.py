# trading/bots/hedge_bot/hedge_bot_data_authorized.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Authorized Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Authorized Module

This module provides comprehensive data authorization and access control
capabilities for the NEXUS Hedge Bot system. It manages permissions,
roles, and access policies for data resources.

The module covers:
- Data Access Control
- Role-Based Access Control
- Permission Management
- Resource Authorization
- Data Access Policies
- User Permissions
- Role Management
- Access Auditing
- Data Classification
- Authorization Reporting
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import re

logger = logging.getLogger(__name__)


# ============================================================
# DATA AUTHORIZED ENUMS
# ============================================================

class AccessLevel(Enum):
    """Access levels"""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


class DataClassification(Enum):
    """Data classification levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class AuthorizationStatus(Enum):
    """Authorization status"""
    GRANTED = "granted"
    DENIED = "denied"
    PENDING = "pending"
    EXPIRED = "expired"


@dataclass
class Permission:
    """Permission definition"""
    id: str
    name: str
    resource: str
    action: str
    access_level: AccessLevel
    description: str
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "resource": self.resource,
            "action": self.action,
            "access_level": self.access_level.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Role:
    """Role definition"""
    id: str
    name: str
    description: str
    permissions: List[Permission]
    is_system: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.to_dict() for p in self.permissions],
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Authorization:
    """Authorization record"""
    id: str
    user_id: str
    resource: str
    access_level: AccessLevel
    status: AuthorizationStatus
    granted_at: datetime
    expires_at: Optional[datetime] = None
    granted_by: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "resource": self.resource,
            "access_level": self.access_level.value,
            "status": self.status.value,
            "granted_at": self.granted_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "granted_by": self.granted_by,
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class AuthorizationReport:
    """Authorization report"""
    id: str
    title: str
    period: Dict[str, str]
    summary: Dict[str, Any]
    authorizations: List[Authorization]
    violations: List[Dict[str, Any]]
    recommendations: List[str]
    generated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "period": self.period,
            "summary": self.summary,
            "authorizations": [a.to_dict() for a in self.authorizations],
            "violations": self.violations,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
        }


# ============================================================
# DATA AUTHORIZED ENGINE
# ============================================================

class DataAuthorizedEngine:
    """
    Comprehensive data authorization engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data authorization engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_access = self.config.get("default_access", AccessLevel.NONE)
        
        # State
        self.permissions: Dict[str, Permission] = {}
        self.roles: Dict[str, Role] = {}
        self.authorizations: Dict[str, Authorization] = {}
        self.user_roles: Dict[str, List[str]] = {}
        
        # Initialize default roles
        self._init_default_roles()
        
        logger.info("Data authorization engine initialized")
    
    # ============================================================
    # DEFAULT ROLES
    # ============================================================
    
    def _init_default_roles(self) -> None:
        """Initialize default roles"""
        # Admin role
        admin_permissions = [
            Permission(
                id="perm_admin_all",
                name="Admin All",
                resource="*",
                action="*",
                access_level=AccessLevel.ADMIN,
                description="Full access to all resources",
            )
        ]
        self.create_role("admin", "Administrator", admin_permissions, is_system=True)
        
        # Trader role
        trader_permissions = [
            Permission(
                id="perm_trade_read",
                name="Trade Read",
                resource="trade",
                action="read",
                access_level=AccessLevel.READ,
                description="Read trade data",
            ),
            Permission(
                id="perm_trade_write",
                name="Trade Write",
                resource="trade",
                action="write",
                access_level=AccessLevel.WRITE,
                description="Create and modify trades",
            ),
        ]
        self.create_role("trader", "Trader", trader_permissions, is_system=True)
        
        # Viewer role
        viewer_permissions = [
            Permission(
                id="perm_view_read",
                name="View Read",
                resource="*",
                action="read",
                access_level=AccessLevel.READ,
                description="Read-only access to all resources",
            )
        ]
        self.create_role("viewer", "Viewer", viewer_permissions, is_system=True)
        
        logger.info("Initialized default roles")
    
    # ============================================================
    # PERMISSION MANAGEMENT
    # ============================================================
    
    def create_permission(
        self,
        name: str,
        resource: str,
        action: str,
        access_level: AccessLevel,
        description: str = ""
    ) -> Permission:
        """
        Create a permission
        
        Args:
            name: Permission name
            resource: Resource pattern
            action: Action pattern
            access_level: Access level
            description: Description
            
        Returns:
            Permission
        """
        permission = Permission(
            id=f"perm_{int(time.time())}_{len(self.permissions)}",
            name=name,
            resource=resource,
            action=action,
            access_level=access_level,
            description=description,
            created_at=datetime.now(),
        )
        
        self.permissions[permission.id] = permission
        return permission
    
    def get_permission(self, permission_id: str) -> Optional[Permission]:
        """
        Get a permission
        
        Args:
            permission_id: Permission ID
            
        Returns:
            Permission or None
        """
        return self.permissions.get(permission_id)
    
    def get_permissions(self) -> List[Permission]:
        """
        Get all permissions
        
        Returns:
            List of permissions
        """
        return list(self.permissions.values())
    
    # ============================================================
    # ROLE MANAGEMENT
    # ============================================================
    
    def create_role(
        self,
        name: str,
        description: str,
        permissions: List[Permission],
        is_system: bool = False
    ) -> Role:
        """
        Create a role
        
        Args:
            name: Role name
            description: Role description
            permissions: List of permissions
            is_system: System role
            
        Returns:
            Role
        """
        role = Role(
            id=f"role_{int(time.time())}_{len(self.roles)}",
            name=name,
            description=description,
            permissions=permissions,
            is_system=is_system,
            created_at=datetime.now(),
        )
        
        self.roles[role.id] = role
        return role
    
    def update_role(
        self,
        role_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Role]:
        """
        Update a role
        
        Args:
            role_id: Role ID
            updates: Updates to apply
            
        Returns:
            Updated role or None
        """
        role = self.roles.get(role_id)
        if not role:
            return None
        
        for key, value in updates.items():
            if hasattr(role, key):
                setattr(role, key, value)
        
        return role
    
    def delete_role(self, role_id: str) -> bool:
        """
        Delete a role
        
        Args:
            role_id: Role ID
            
        Returns:
            True if deleted
        """
        if role_id in self.roles:
            del self.roles[role_id]
            return True
        return False
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """
        Get a role
        
        Args:
            role_id: Role ID
            
        Returns:
            Role or None
        """
        return self.roles.get(role_id)
    
    def get_roles(self) -> List[Role]:
        """
        Get all roles
        
        Returns:
            List of roles
        """
        return list(self.roles.values())
    
    # ============================================================
    # USER AUTHORIZATION
    # ============================================================
    
    def assign_role(self, user_id: str, role_id: str) -> bool:
        """
        Assign a role to a user
        
        Args:
            user_id: User ID
            role_id: Role ID
            
        Returns:
            True if assigned
        """
        role = self.roles.get(role_id)
        if not role:
            return False
        
        if user_id not in self.user_roles:
            self.user_roles[user_id] = []
        
        if role_id not in self.user_roles[user_id]:
            self.user_roles[user_id].append(role_id)
            return True
        
        return False
    
    def remove_role(self, user_id: str, role_id: str) -> bool:
        """
        Remove a role from a user
        
        Args:
            user_id: User ID
            role_id: Role ID
            
        Returns:
            True if removed
        """
        if user_id not in self.user_roles:
            return False
        
        if role_id in self.user_roles[user_id]:
            self.user_roles[user_id].remove(role_id)
            return True
        
        return False
    
    def get_user_roles(self, user_id: str) -> List[Role]:
        """
        Get roles for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of roles
        """
        if user_id not in self.user_roles:
            return []
        
        return [self.roles[role_id] for role_id in self.user_roles[user_id] if role_id in self.roles]
    
    def get_user_permissions(self, user_id: str) -> List[Permission]:
        """
        Get permissions for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of permissions
        """
        roles = self.get_user_roles(user_id)
        permissions = []
        
        for role in roles:
            permissions.extend(role.permissions)
        
        return list(set(permissions))
    
    # ============================================================
    # RESOURCE AUTHORIZATION
    # ============================================================
    
    def check_authorization(
        self,
        user_id: str,
        resource: str,
        action: str,
        required_level: AccessLevel = AccessLevel.READ
    ) -> AuthorizationStatus:
        """
        Check if user is authorized for a resource
        
        Args:
            user_id: User ID
            resource: Resource pattern
            action: Action
            required_level: Required access level
            
        Returns:
            AuthorizationStatus
        """
        permissions = self.get_user_permissions(user_id)
        
        for permission in permissions:
            # Check if permission matches resource
            if not self._match_pattern(resource, permission.resource):
                continue
            
            # Check if permission matches action
            if not self._match_pattern(action, permission.action):
                continue
            
            # Check access level
            if self._access_level_satisfies(permission.access_level, required_level):
                return AuthorizationStatus.GRANTED
        
        return AuthorizationStatus.DENIED
    
    def _match_pattern(self, value: str, pattern: str) -> bool:
        """
        Match a pattern
        
        Args:
            value: Value to match
            pattern: Pattern to match against
            
        Returns:
            True if matches
        """
        if pattern == "*":
            return True
        return re.match(pattern, value) is not None
    
    def _access_level_satisfies(self, level: AccessLevel, required: AccessLevel) -> bool:
        """
        Check if access level satisfies requirement
        
        Args:
            level: Access level
            required: Required access level
            
        Returns:
            True if satisfies
        """
        level_order = {
            AccessLevel.NONE: 0,
            AccessLevel.READ: 1,
            AccessLevel.WRITE: 2,
            AccessLevel.ADMIN: 3,
            AccessLevel.OWNER: 4,
        }
        
        return level_order.get(level, 0) >= level_order.get(required, 0)
    
    # ============================================================
    # DATA CLASSIFICATION
    # ============================================================
    
    def classify_data(self, data: Dict[str, Any]) -> DataClassification:
        """
        Classify data based on sensitivity
        
        Args:
            data: Data to classify
            
        Returns:
            DataClassification
        """
        # Check for sensitive keywords
        sensitive_keywords = ["password", "key", "secret", "token", "api", "auth"]
        
        data_str = json.dumps(data).lower()
        
        for keyword in sensitive_keywords:
            if keyword in data_str:
                return DataClassification.CONFIDENTIAL
        
        # Check for PII
        pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{4} \d{4} \d{4} \d{4}\b',  # Credit card
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        ]
        
        for pattern in pii_patterns:
            if re.search(pattern, data_str):
                return DataClassification.RESTRICTED
        
        return DataClassification.INTERNAL
    
    # ============================================================
    # REPORTING
    # ============================================================
    
    def generate_authorization_report(self) -> AuthorizationReport:
        """
        Generate authorization report
        
        Returns:
            AuthorizationReport
        """
        users = list(self.user_roles.keys())
        
        summary = {
            "total_users": len(users),
            "total_roles": len(self.roles),
            "total_permissions": len(self.permissions),
            "role_distribution": {
                role.name: len([u for u, r in self.user_roles.items() if role.id in r])
                for role in self.roles.values()
            },
        }
        
        report = AuthorizationReport(
            id=f"auth_report_{int(time.time())}",
            title="Authorization Report",
            period={
                "start": (datetime.now() - timedelta(days=30)).isoformat(),
                "end": datetime.now().isoformat(),
            },
            summary=summary,
            authorizations=[],  # Would need to track authorizations
            violations=[],
            recommendations=["Review inactive users", "Audit role assignments"],
            generated_at=datetime.now(),
        )
        
        return report
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get authorization statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_roles": len(self.roles),
            "total_permissions": len(self.permissions),
            "total_users": len(self.user_roles),
            "role_distribution": {
                role.name: len([u for u, r in self.user_roles.items() if role.id in r])
                for role in self.roles.values()
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "AccessLevel",
    "DataClassification",
    "AuthorizationStatus",
    
    # Dataclasses
    "Permission",
    "Role",
    "Authorization",
    "AuthorizationReport",
    
    # Classes
    "DataAuthorizedEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
