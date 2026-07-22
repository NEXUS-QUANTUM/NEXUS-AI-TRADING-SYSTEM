"""
NEXUS AI TRADING SYSTEM - HEDGE BOT AUDIT MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données d'audit pour le Hedge Bot.
Définition des entités d'audit, logs, et conformité.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, DateTime, Numeric, Integer, Boolean, 
    ForeignKey, Text, JSON, Enum as SQLEnum, Index, LargeBinary
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..utils.helpers import safe_decimal, safe_float

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class AuditSeverity(Enum):
    """Niveaux de sévérité d'audit."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


class AuditCategory(Enum):
    """Catégories d'audit."""
    SYSTEM = "system"
    USER = "user"
    TRADING = "trading"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    CONFIGURATION = "configuration"
    DATA = "data"
    NETWORK = "network"
    APPLICATION = "application"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"


class AuditAction(Enum):
    """Actions d'audit."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    LOGIN = "login"
    LOGOUT = "logout"
    APPROVE = "approve"
    REJECT = "reject"
    SUSPEND = "suspend"
    ACTIVATE = "activate"
    MODIFY = "modify"
    TRANSFER = "transfer"
    TRADE = "trade"
    CONFIG = "config"
    BACKUP = "backup"
    RESTORE = "restore"
    EXPORT = "export"
    IMPORT = "import"
    AUDIT = "audit"
    REVIEW = "review"


class ComplianceStatus(Enum):
    """Statuts de conformité."""
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"
    REVIEW = "review"
    EXEMPT = "exempt"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class AuditLogModel(Base):
    """Modèle de log d'audit."""
    __tablename__ = "audit_logs"

    log_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=True)
    session_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    category = Column(SQLEnum(AuditCategory), nullable=False)
    action = Column(SQLEnum(AuditAction), nullable=False)
    severity = Column(SQLEnum(AuditSeverity), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    message = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    correlation_id = Column(String(36), nullable=True)
    source = Column(String(50), nullable=True)
    hostname = Column(String(255), nullable=True)
    process_id = Column(Integer, nullable=True)
    thread_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_category", "category"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_severity", "severity"),
        Index("idx_audit_logs_correlation", "correlation_id"),
        Index("idx_audit_logs_created_at", "created_at"),
    )


class ComplianceRuleModel(Base):
    """Modèle de règle de conformité."""
    __tablename__ = "compliance_rules"

    rule_id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(SQLEnum(AuditCategory), nullable=False)
    condition = Column(Text, nullable=False)
    severity = Column(SQLEnum(AuditSeverity), nullable=False)
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_compliance_rules_category", "category"),
        Index("idx_compliance_rules_enabled", "enabled"),
    )


class ComplianceViolationModel(Base):
    """Modèle de violation de conformité."""
    __tablename__ = "compliance_violations"

    violation_id = Column(String(36), primary_key=True)
    rule_id = Column(String(36), ForeignKey("compliance_rules.rule_id"), nullable=False)
    user_id = Column(String(36), nullable=True)
    session_id = Column(String(36), nullable=True)
    audit_log_id = Column(String(36), ForeignKey("audit_logs.log_id"), nullable=True)
    severity = Column(SQLEnum(AuditSeverity), nullable=False)
    status = Column(SQLEnum(ComplianceStatus), nullable=False)
    details = Column(JSON, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(36), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

    # Relations
    rule = relationship("ComplianceRuleModel")
    audit_log = relationship("AuditLogModel")

    __table_args__ = (
        Index("idx_compliance_violations_rule_id", "rule_id"),
        Index("idx_compliance_violations_user_id", "user_id"),
        Index("idx_compliance_violations_status", "status"),
        Index("idx_compliance_violations_created_at", "created_at"),
    )


class AuditReportModel(Base):
    """Modèle de rapport d'audit."""
    __tablename__ = "audit_reports"

    report_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    report_type = Column(String(50), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    status = Column(SQLEnum(ComplianceStatus), nullable=False)
    content = Column(JSON, nullable=False)
    summary = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(36), nullable=True)

    __table_args__ = (
        Index("idx_audit_reports_user_id", "user_id"),
        Index("idx_audit_reports_type", "report_type"),
        Index("idx_audit_reports_period", "period_start", "period_end"),
        Index("idx_audit_reports_status", "status"),
    )


class DataRetentionPolicyModel(Base):
    """Modèle de politique de rétention des données."""
    __tablename__ = "data_retention_policies"

    policy_id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    data_type = Column(String(50), nullable=False)
    retention_days = Column(Integer, nullable=False)
    archive_days = Column(Integer, nullable=True)
    delete_after_archive = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_retention_policies_data_type", "data_type"),
        Index("idx_retention_policies_enabled", "enabled"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class AuditLog:
    """Log d'audit."""
    log_id: UUID
    user_id: Optional[UUID]
    session_id: Optional[UUID]
    ip_address: Optional[str]
    user_agent: Optional[str]
    category: AuditCategory
    action: AuditAction
    severity: AuditSeverity
    resource_type: Optional[str]
    resource_id: Optional[str]
    old_value: Optional[Any]
    new_value: Optional[Any]
    message: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[UUID] = None
    source: Optional[str] = None
    hostname: Optional[str] = None
    process_id: Optional[int] = None
    thread_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "log_id": str(self.log_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "session_id": str(self.session_id) if self.session_id else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "category": self.category.value,
            "action": self.action.value,
            "severity": self.severity.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "message": self.message,
            "metadata": self.metadata,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "source": self.source,
            "hostname": self.hostname,
            "process_id": self.process_id,
            "thread_id": self.thread_id,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ComplianceRule:
    """Règle de conformité."""
    rule_id: UUID
    name: str
    description: Optional[str]
    category: AuditCategory
    condition: str
    severity: AuditSeverity
    enabled: bool
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "rule_id": str(self.rule_id),
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "condition": self.condition,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "priority": self.priority,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class ComplianceViolation:
    """Violation de conformité."""
    violation_id: UUID
    rule_id: UUID
    user_id: Optional[UUID]
    session_id: Optional[UUID]
    audit_log_id: Optional[UUID]
    severity: AuditSeverity
    status: ComplianceStatus
    details: Optional[Dict[str, Any]]
    resolved_at: Optional[datetime]
    resolved_by: Optional[UUID]
    resolution_notes: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "violation_id": str(self.violation_id),
            "rule_id": str(self.rule_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "session_id": str(self.session_id) if self.session_id else None,
            "audit_log_id": str(self.audit_log_id) if self.audit_log_id else None,
            "severity": self.severity.value,
            "status": self.status.value,
            "details": self.details,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": str(self.resolved_by) if self.resolved_by else None,
            "resolution_notes": self.resolution_notes,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class AuditReport:
    """Rapport d'audit."""
    report_id: UUID
    user_id: UUID
    report_type: str
    period_start: datetime
    period_end: datetime
    status: ComplianceStatus
    content: Dict[str, Any]
    summary: Optional[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "report_id": str(self.report_id),
            "user_id": str(self.user_id),
            "report_type": self.report_type,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "status": self.status.value,
            "content": self.content,
            "summary": self.summary,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": str(self.reviewed_by) if self.reviewed_by else None
        }


@dataclass
class DataRetentionPolicy:
    """Politique de rétention des données."""
    policy_id: UUID
    name: str
    description: Optional[str]
    data_type: str
    retention_days: int
    archive_days: Optional[int]
    delete_after_archive: bool
    enabled: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "policy_id": str(self.policy_id),
            "name": self.name,
            "description": self.description,
            "data_type": self.data_type,
            "retention_days": self.retention_days,
            "archive_days": self.archive_days,
            "delete_after_archive": self.delete_after_archive,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_audit_log(
    user_id: Optional[UUID],
    category: AuditCategory,
    action: AuditAction,
    severity: AuditSeverity,
    message: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    old_value: Optional[Any] = None,
    new_value: Optional[Any] = None,
    metadata: Optional[Dict] = None,
    correlation_id: Optional[UUID] = None
) -> AuditLog:
    """
    Crée un log d'audit.

    Args:
        user_id: ID de l'utilisateur
        category: Catégorie
        action: Action
        severity: Sévérité
        message: Message
        ip_address: Adresse IP
        user_agent: User agent
        resource_type: Type de ressource
        resource_id: ID de la ressource
        old_value: Ancienne valeur
        new_value: Nouvelle valeur
        metadata: Métadonnées
        correlation_id: ID de corrélation

    Returns:
        Log d'audit
    """
    return AuditLog(
        log_id=uuid4(),
        user_id=user_id,
        session_id=None,
        ip_address=ip_address,
        user_agent=user_agent,
        category=category,
        action=action,
        severity=severity,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old_value,
        new_value=new_value,
        message=message,
        metadata=metadata or {},
        correlation_id=correlation_id
    )


def create_compliance_rule(
    name: str,
    category: AuditCategory,
    condition: str,
    severity: AuditSeverity,
    description: Optional[str] = None,
    enabled: bool = True,
    priority: int = 0,
    metadata: Optional[Dict] = None
) -> ComplianceRule:
    """
    Crée une règle de conformité.

    Args:
        name: Nom de la règle
        category: Catégorie
        condition: Condition
        severity: Sévérité
        description: Description
        enabled: Activée
        priority: Priorité
        metadata: Métadonnées

    Returns:
        Règle de conformité
    """
    return ComplianceRule(
        rule_id=uuid4(),
        name=name,
        description=description,
        category=category,
        condition=condition,
        severity=severity,
        enabled=enabled,
        priority=priority,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "AuditSeverity",
    "AuditCategory",
    "AuditAction",
    "ComplianceStatus",
    "AuditLogModel",
    "ComplianceRuleModel",
    "ComplianceViolationModel",
    "AuditReportModel",
    "DataRetentionPolicyModel",
    "AuditLog",
    "ComplianceRule",
    "ComplianceViolation",
    "AuditReport",
    "DataRetentionPolicy",
    "create_audit_log",
    "create_compliance_rule"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles d'audit."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT AUDIT MODELS")
    print("=" * 60)

    # Création d'un log d'audit
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📝 Création d'un log d'audit...")
    
    log = create_audit_log(
        user_id=user_id,
        category=AuditCategory.USER,
        action=AuditAction.LOGIN,
        severity=AuditSeverity.INFO,
        message="Connexion utilisateur réussie",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0",
        metadata={"method": "api_key"}
    )

    print(f"   ID: {log.log_id}")
    print(f"   Catégorie: {log.category.value}")
    print(f"   Action: {log.action.value}")
    print(f"   Sévérité: {log.severity.value}")
    print(f"   Message: {log.message}")

    # Création d'une règle de conformité
    print(f"\n📋 Création d'une règle de conformité...")
    
    rule = create_compliance_rule(
        name="KYC Verification",
        category=AuditCategory.COMPLIANCE,
        condition="user.kyc.verified == false",
        severity=AuditSeverity.CRITICAL,
        description="Vérification KYC requise",
        enabled=True,
        priority=10
    )

    print(f"   ID: {rule.rule_id}")
    print(f"   Nom: {rule.name}")
    print(f"   Condition: {rule.condition}")
    print(f"   Sévérité: {rule.severity.value}")

    # Création d'une violation de conformité
    print(f"\n⚠️ Création d'une violation de conformité...")
    
    violation = ComplianceViolation(
        violation_id=uuid4(),
        rule_id=rule.rule_id,
        user_id=user_id,
        severity=AuditSeverity.CRITICAL,
        status=ComplianceStatus.PENDING,
        details={"reason": "KYC non vérifié"},
        created_at=datetime.now()
    )

    print(f"   ID: {violation.violation_id}")
    print(f"   Statut: {violation.status.value}")

    # Politique de rétention
    print(f"\n🗄️ Création d'une politique de rétention...")
    
    policy = DataRetentionPolicy(
        policy_id=uuid4(),
        name="Audit Logs Retention",
        description="Conservation des logs d'audit",
        data_type="audit_logs",
        retention_days=365,
        archive_days=180,
        delete_after_archive=True,
        enabled=True
    )

    print(f"   ID: {policy.policy_id}")
    print(f"   Rétention: {policy.retention_days} jours")
    print(f"   Archivage: {policy.archive_days} jours")

    print("\n" + "=" * 60)
    print("Audit Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
