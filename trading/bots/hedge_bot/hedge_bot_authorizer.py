# trading/bots/hedge_bot/hedge_bot_authorizer.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Authorizer Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Authorizer Module

This module provides comprehensive authorization and access control
capabilities for the NEXUS Hedge Bot system. It implements role-based
access control (RBAC), attribute-based access control (ABAC), and
policy-based access control.

The module covers:
- Role-Based Access Control (RBAC)
- Attribute-Based Access Control (ABAC)
- Policy-Based Access Control
- Permission Management
- Resource Management
- Action Management
- Dynamic Authorization
- Policy Enforcement
- Access Auditing
- Role Hierarchy
- Permission Inheritance
- Fine-Grained Access Control
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================
# AUTHORIZER ENUMS
# ============================================================

class ResourceType(Enum):
    """Resource types"""
    TRADE = "trade"
    ORDER = "order"
    POSITION = "position"
    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    RISK = "risk"
    CONFIG = "config"
    USER = "user"
    API_KEY = "api_key"
    AUDIT = "audit"
    REPORT = "report"
    SYSTEM = "system"


class ActionType(Enum):
    """Action types"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    APPROVE = "approve"
    REJECT = "reject"
    VIEW = "view"
    MODIFY = "modify"
    ADMIN = "admin"


class AccessDecision(Enum):
    """Access decisions"""
    ALLOW = "allow"
    DENY = "deny"
    ABSTAIN = "abstain"
    NOT_APPLICABLE = "not_applicable"


# ============================================================
# AUTHORIZER DATACLASSES
# ============================================================

@dataclass
class Permission:
    """Permission definition"""
    id: str
    name: str
    resource: ResourceType
    actions: List[ActionType]
    description: str
    conditions: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "resource": self.resource.value,
            "actions": [a.value for a in self.actions],
            "description": self.description,
            "conditions": self.conditions,
        }


@dataclass
class Role:
    """Role definition"""
    id: str
    name: str
    description: str
    permissions: List[Permission]
    parent_roles: List[str] = field(default_factory=list)
    is_system: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.to_dict() for p in self.permissions],
            "parent_roles": self.parent_roles,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Policy:
    """Policy definition"""
    id: str
    name: str
    description: str
    priority: int
    effect: AccessDecision
    conditions: Dict[str, Any]
    resources: List[str]
    actions: List[str]
    roles: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "effect": self.effect.value,
            "conditions": self.conditions,
            "resources": self.resources,
            "actions": self.actions,
            "roles": self.roles,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class AccessRequest:
    """Access request"""
    user_id: str
    user_roles: List[str]
    resource: ResourceType
    resource_id: str
    action: ActionType
    attributes: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "user_roles": self.user_roles,
            "resource": self.resource.value,
            "resource_id": self.resource_id,
            "action": self.action.value,
            "attributes": self.attributes,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AccessResult:
    """Access result"""
    decision: AccessDecision
    reason: str
    policies_applied: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "policies_applied": self.policies_applied,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# AUTHORIZER ENGINE
# ============================================================

class AuthorizerEngine:
    """
    Comprehensive authorizer engine for the hedge bot
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the authorizer engine
        
        Args:
            config: Configuration dictionary
        """
        if hasattr(self, '_initialized'):
            return
        
        self.config = config or {}
        self.default_effect = AccessDecision.DENY
        self.enable_audit = self.config.get("enable_audit", True)
        self.enable_policy_engine = self.config.get("enable_policy_engine", True)
        
        # State
        self.roles: Dict[str, Role] = {}
        self.permissions: Dict[str, Permission] = {}
        self.policies: Dict[str, Policy] = {}
        self.audit_log: List[AccessResult] = []
        
        # Initialize default roles
        self._init_default_roles()
        
        self._initialized = True
        logger.info("Authorizer engine initialized")
    
    # ============================================================
    # ROLE MANAGEMENT
    # ============================================================
    
    def _init_default_roles(self) -> None:
        """Initialize default roles"""
        # Admin role
        admin_permissions = [
            Permission(
                id="perm_admin",
                name="Administrator",
                resource=ResourceType.SYSTEM,
                actions=[ActionType.ADMIN],
                description="Full system access",
            )
        ]
        
        admin_role = Role(
            id="role_admin",
            name="Administrator",
            description="Full system administrator",
            permissions=admin_permissions,
            is_system=True,
        )
        self.roles[admin_role.id] = admin_role
        
        # Trader role
        trader_permissions = [
            Permission(
                id="perm_trade",
                name="Trade",
                resource=ResourceType.TRADE,
                actions=[ActionType.CREATE, ActionType.READ, ActionType.UPDATE, ActionType.EXECUTE],
                description="Trade execution",
            ),
            Permission(
                id="perm_order",
                name="Order",
                resource=ResourceType.ORDER,
                actions=[ActionType.CREATE, ActionType.READ, ActionType.UPDATE, ActionType.DELETE],
                description="Order management",
            ),
            Permission(
                id="perm_position",
                name="Position",
                resource=ResourceType.POSITION,
                actions=[ActionType.READ, ActionType.UPDATE],
                description="Position management",
            ),
        ]
        
        trader_role = Role(
            id="role_trader",
            name="Trader",
            description="Trading operations",
            permissions=trader_permissions,
            is_system=True,
        )
        self.roles[trader_role.id] = trader_role
        
        # Viewer role
        viewer_permissions = [
            Permission(
                id="perm_view",
                name="View",
                resource=ResourceType.POSITION,
                actions=[ActionType.VIEW, ActionType.READ],
                description="View-only access",
            ),
            Permission(
                id="perm_portfolio_view",
                name="Portfolio View",
                resource=ResourceType.PORTFOLIO,
                actions=[ActionType.VIEW, ActionType.READ],
                description="Portfolio view",
            ),
        ]
        
        viewer_role = Role(
            id="role_viewer",
            name="Viewer",
            description="Read-only access",
            permissions=viewer_permissions,
            is_system=True,
        )
        self.roles[viewer_role.id] = viewer_role
        
        # Auditor role
        auditor_permissions = [
            Permission(
                id="perm_audit",
                name="Audit",
                resource=ResourceType.AUDIT,
                actions=[ActionType.READ, ActionType.VIEW],
                description="Audit access",
            ),
            Permission(
                id="perm_report",
                name="Report",
                resource=ResourceType.REPORT,
                actions=[ActionType.READ, ActionType.VIEW],
                description="Report access",
            ),
        ]
        
        auditor_role = Role(
            id="role_auditor",
            name="Auditor",
            description="Audit and compliance",
            permissions=auditor_permissions,
            is_system=True,
        )
        self.roles[auditor_role.id] = auditor_role
    
    def create_role(
        self,
        name: str,
        description: str,
        permissions: List[Dict[str, Any]],
        parent_roles: Optional[List[str]] = None
    ) -> Role:
        """
        Create a new role
        
        Args:
            name: Role name
            description: Role description
            permissions: List of permissions
            parent_roles: Parent role IDs
            
        Returns:
            Role
        """
        # Create permissions
        permission_objects = []
        for perm_data in permissions:
            perm = Permission(
                id=f"perm_{int(time.time())}_{len(self.permissions)}",
                name=perm_data.get("name", "Permission"),
                resource=ResourceType(perm_data.get("resource", "system")),
                actions=[ActionType(a) for a in perm_data.get("actions", ["read"])],
                description=perm_data.get("description", ""),
                conditions=perm_data.get("conditions"),
            )
            self.permissions[perm.id] = perm
            permission_objects.append(perm)
        
        # Create role
        role = Role(
            id=f"role_{int(time.time())}_{len(self.roles)}",
            name=name,
            description=description,
            permissions=permission_objects,
            parent_roles=parent_roles or [],
        )
        
        self.roles[role.id] = role
        logger.info(f"Created role: {name}")
        return role
    
    def update_role(self, role_id: str, updates: Dict[str, Any]) -> Optional[Role]:
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
        
        if "name" in updates:
            role.name = updates["name"]
        if "description" in updates:
            role.description = updates["description"]
        if "parent_roles" in updates:
            role.parent_roles = updates["parent_roles"]
        
        role.updated_at = datetime.now()
        logger.info(f"Updated role: {role.name}")
        return role
    
    def delete_role(self, role_id: str) -> bool:
        """
        Delete a role
        
        Args:
            role_id: Role ID
            
        Returns:
            True if deleted
        """
        role = self.roles.get(role_id)
        if not role:
            return False
        
        if role.is_system:
            logger.warning(f"Cannot delete system role: {role.name}")
            return False
        
        del self.roles[role_id]
        logger.info(f"Deleted role: {role.name}")
        return True
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """
        Get a role by ID
        
        Args:
            role_id: Role ID
            
        Returns:
            Role or None
        """
        return self.roles.get(role_id)
    
    def get_roles_by_user(self, user_id: str) -> List[Role]:
        """
        Get roles for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of roles
        """
        # This would normally query a user-role mapping
        # For simplicity, we return all roles
        return list(self.roles.values())
    
    def get_user_permissions(self, user_roles: List[str]) -> Set[Permission]:
        """
        Get all permissions for a set of roles
        
        Args:
            user_roles: List of role IDs
            
        Returns:
            Set of permissions
        """
        permissions = set()
        
        for role_id in user_roles:
            role = self.roles.get(role_id)
            if role:
                # Add role permissions
                permissions.update(role.permissions)
                
                # Add parent role permissions
                for parent_id in role.parent_roles:
                    parent = self.roles.get(parent_id)
                    if parent:
                        permissions.update(parent.permissions)
        
        return permissions
    
    # ============================================================
    # PERMISSION MANAGEMENT
    # ============================================================
    
    def create_permission(
        self,
        name: str,
        resource: ResourceType,
        actions: List[ActionType],
        description: str,
        conditions: Optional[Dict[str, Any]] = None
    ) -> Permission:
        """
        Create a permission
        
        Args:
            name: Permission name
            resource: Resource type
            actions: List of actions
            description: Permission description
            conditions: Condition rules
            
        Returns:
            Permission
        """
        perm = Permission(
            id=f"perm_{int(time.time())}_{len(self.permissions)}",
            name=name,
            resource=resource,
            actions=actions,
            description=description,
            conditions=conditions,
        )
        
        self.permissions[perm.id] = perm
        logger.info(f"Created permission: {name}")
        return perm
    
    def delete_permission(self, permission_id: str) -> bool:
        """
        Delete a permission
        
        Args:
            permission_id: Permission ID
            
        Returns:
            True if deleted
        """
        if permission_id in self.permissions:
            del self.permissions[permission_id]
            logger.info(f"Deleted permission: {permission_id}")
            return True
        return False
    
    # ============================================================
    # POLICY MANAGEMENT
    # ============================================================
    
    def create_policy(
        self,
        name: str,
        description: str,
        effect: AccessDecision,
        conditions: Dict[str, Any],
        resources: List[str],
        actions: List[str],
        roles: List[str],
        priority: int = 100
    ) -> Policy:
        """
        Create a policy
        
        Args:
            name: Policy name
            description: Policy description
            effect: Access decision
            conditions: Conditions
            resources: Resource patterns
            actions: Action patterns
            roles: Role patterns
            priority: Policy priority
            
        Returns:
            Policy
        """
        policy = Policy(
            id=f"policy_{int(time.time())}_{len(self.policies)}",
            name=name,
            description=description,
            priority=priority,
            effect=effect,
            conditions=conditions,
            resources=resources,
            actions=actions,
            roles=roles,
        )
        
        self.policies[policy.id] = policy
        logger.info(f"Created policy: {name}")
        return policy
    
    def update_policy(self, policy_id: str, updates: Dict[str, Any]) -> Optional[Policy]:
        """
        Update a policy
        
        Args:
            policy_id: Policy ID
            updates: Updates to apply
            
        Returns:
            Updated policy or None
        """
        policy = self.policies.get(policy_id)
        if not policy:
            return None
        
        for key, value in updates.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
        
        policy.updated_at = datetime.now()
        logger.info(f"Updated policy: {policy.name}")
        return policy
    
    def delete_policy(self, policy_id: str) -> bool:
        """
        Delete a policy
        
        Args:
            policy_id: Policy ID
            
        Returns:
            True if deleted
        """
        if policy_id in self.policies:
            del self.policies[policy_id]
            logger.info(f"Deleted policy: {policy_id}")
            return True
        return False
    
    def get_policies(self) -> List[Policy]:
        """
        Get all policies sorted by priority
        
        Returns:
            List of policies
        """
        return sorted(self.policies.values(), key=lambda p: p.priority)
    
    # ============================================================
    # AUTHORIZATION
    # ============================================================
    
    def authorize(
        self,
        user_id: str,
        user_roles: List[str],
        resource: ResourceType,
        resource_id: str,
        action: ActionType,
        attributes: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AccessResult:
        """
        Authorize an access request
        
        Args:
            user_id: User ID
            user_roles: User roles
            resource: Resource type
            resource_id: Resource ID
            action: Action
            attributes: Request attributes
            context: Request context
            
        Returns:
            AccessResult
        """
        request = AccessRequest(
            user_id=user_id,
            user_roles=user_roles,
            resource=resource,
            resource_id=resource_id,
            action=action,
            attributes=attributes or {},
            context=context or {},
        )
        
        # Check policies
        if self.enable_policy_engine:
            result = self._evaluate_policies(request)
            if result.decision != AccessDecision.ABSTAIN:
                self._audit(request, result)
                return result
        
        # Check RBAC
        permissions = self.get_user_permissions(user_roles)
        if self._has_permission(permissions, resource, action):
            result = AccessResult(
                decision=AccessDecision.ALLOW,
                reason="Permission granted",
                policies_applied=["rbac"],
            )
            self._audit(request, result)
            return result
        
        # Default deny
        result = AccessResult(
            decision=self.default_effect,
            reason="No policy or permission matched",
            policies_applied=[],
        )
        self._audit(request, result)
        return result
    
    def _evaluate_policies(self, request: AccessRequest) -> AccessResult:
        """
        Evaluate policies for a request
        
        Args:
            request: Access request
            
        Returns:
            AccessResult
        """
        applicable_policies = []
        
        for policy in self.get_policies():
            if self._policy_applies(policy, request):
                applicable_policies.append(policy)
        
        if not applicable_policies:
            return AccessResult(
                decision=AccessDecision.ABSTAIN,
                reason="No applicable policies",
                policies_applied=[],
            )
        
        # Apply policies in priority order
        for policy in applicable_policies:
            if self._matches_conditions(policy.conditions, request):
                return AccessResult(
                    decision=policy.effect,
                    reason=f"Policy matched: {policy.name}",
                    policies_applied=[policy.id],
                )
        
        return AccessResult(
            decision=AccessDecision.ABSTAIN,
            reason="No policy conditions matched",
            policies_applied=[p.id for p in applicable_policies],
        )
    
    def _policy_applies(self, policy: Policy, request: AccessRequest) -> bool:
        """
        Check if a policy applies to a request
        
        Args:
            policy: Policy
            request: Access request
            
        Returns:
            True if applies
        """
        # Check roles
        if policy.roles:
            role_match = any(
                any(re.match(pattern, role) for pattern in policy.roles)
                for role in request.user_roles
            )
            if not role_match:
                return False
        
        # Check resources
        if policy.resources:
            resource_match = any(
                re.match(pattern, request.resource.value)
                for pattern in policy.resources
            )
            if not resource_match:
                return False
        
        # Check actions
        if policy.actions:
            action_match = any(
                re.match(pattern, request.action.value)
                for pattern in policy.actions
            )
            if not action_match:
                return False
        
        return True
    
    def _matches_conditions(self, conditions: Dict[str, Any], request: AccessRequest) -> bool:
        """
        Check if conditions match
        
        Args:
            conditions: Condition rules
            request: Access request
            
        Returns:
            True if matches
        """
        if not conditions:
            return True
        
        for key, value in conditions.items():
            if key == "resource":
                if request.resource.value != value:
                    return False
            elif key == "action":
                if request.action.value != value:
                    return False
            elif key == "attributes":
                for attr_key, attr_value in value.items():
                    if request.attributes.get(attr_key) != attr_value:
                        return False
            elif key == "context":
                for ctx_key, ctx_value in value.items():
                    if request.context.get(ctx_key) != ctx_value:
                        return False
            elif key == "user_id":
                if request.user_id != value:
                    return False
            else:
                # Check if attribute exists in request
                if request.attributes.get(key) != value:
                    return False
        
        return True
    
    def _has_permission(
        self,
        permissions: Set[Permission],
        resource: ResourceType,
        action: ActionType
    ) -> bool:
        """
        Check if permissions include access
        
        Args:
            permissions: Set of permissions
            resource: Resource type
            action: Action
            
        Returns:
            True if has permission
        """
        for perm in permissions:
            if perm.resource == resource and action in perm.actions:
                # Check conditions
                if perm.conditions:
                    # Simplified condition check
                    if all(
                        perm.conditions.get(k) == v
                        for k, v in perm.conditions.items()
                    ):
                        return True
                else:
                    return True
        return False
    
    # ============================================================
    # ACCESS AUDITING
    # ============================================================
    
    def _audit(self, request: AccessRequest, result: AccessResult) -> None:
        """
        Audit an access request
        
        Args:
            request: Access request
            result: Access result
        """
        if self.enable_audit:
            self.audit_log.append(result)
            logger.debug(
                f"Access audit: {request.user_id} -> {request.action.value} "
                f"{request.resource.value}/{request.resource_id} = {result.decision.value}"
            )
    
    def get_audit_log(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        decision: Optional[AccessDecision] = None
    ) -> List[AccessResult]:
        """
        Get audit log
        
        Args:
            start_time: Start time
            end_time: End time
            user_id: User ID filter
            decision: Decision filter
            
        Returns:
            List of access results
        """
        results = self.audit_log
        
        if start_time:
            results = [r for r in results if r.timestamp >= start_time]
        if end_time:
            results = [r for r in results if r.timestamp <= end_time]
        if user_id:
            results = [r for r in results if r.metadata.get("user_id") == user_id]
        if decision:
            results = [r for r in results if r.decision == decision]
        
        return results
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get authorizer statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_roles": len(self.roles),
            "total_permissions": len(self.permissions),
            "total_policies": len(self.policies),
            "total_audit_entries": len(self.audit_log),
            "roles": {name: role.to_dict() for name, role in self.roles.items()},
        }
    
    def clear_audit_log(self) -> None:
        """Clear the audit log"""
        self.audit_log.clear()
        logger.info("Audit log cleared")
    
    def export_policies(self) -> Dict[str, Any]:
        """
        Export all policies
        
        Returns:
            Dictionary of policies
        """
        return {
            "roles": {k: v.to_dict() for k, v in self.roles.items()},
            "permissions": {k: v.to_dict() for k, v in self.permissions.items()},
            "policies": {k: v.to_dict() for k, v in self.policies.items()},
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "ResourceType",
    "ActionType",
    "AccessDecision",
    
    # Dataclasses
    "Permission",
    "Role",
    "Policy",
    "AccessRequest",
    "AccessResult",
    
    # Classes
    "AuthorizerEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
