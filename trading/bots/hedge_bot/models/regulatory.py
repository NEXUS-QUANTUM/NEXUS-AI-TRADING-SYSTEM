"""
NEXUS AI TRADING SYSTEM - HEDGE BOT REGULATORY MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données réglementaires pour le Hedge Bot.
Définition des entités de conformité, rapports, et métriques réglementaires.

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
    ForeignKey, Text, JSON, Enum as SQLEnum, Index, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..utils.helpers import safe_decimal, safe_float

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class RegulatoryBody(Enum):
    """Autorités réglementaires."""
    SEC = "sec"
    CFTC = "cftc"
    FINRA = "finra"
    ESMA = "esma"
    FCA = "fca"
    AMF = "amf"
    BaFin = "bafin"
    MAS = "mas"
    HKMA = "hkma"
    JFSA = "jfsa"
    AUSTRAC = "austrac"
    G20 = "g20"
    FATF = "fatf"


class ComplianceType(Enum):
    """Types de conformité."""
    KYC = "kyc"
    AML = "aml"
    CTF = "ctf"
    MIFID = "mifid"
    EMIR = "emir"
    SFTR = "sftr"
    GDPR = "gdpr"
    CCPA = "ccpa"
    SOC2 = "soc2"
    ISO27001 = "iso27001"


class ComplianceStatus(Enum):
    """Statuts de conformité."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    EXEMPT = "exempt"
    UNDER_REVIEW = "under_review"
    VIOLATED = "violated"


class ReportType(Enum):
    """Types de rapports."""
    REGULATORY = "regulatory"
    COMPLIANCE = "compliance"
    AUDIT = "audit"
    TAX = "tax"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    RISK = "risk"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class RegulatoryReportModel(Base):
    """Modèle de rapport réglementaire."""
    __tablename__ = "regulatory_reports"

    report_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    report_type = Column(SQLEnum(ReportType), nullable=False)
    regulatory_body = Column(SQLEnum(RegulatoryBody), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    status = Column(SQLEnum(ComplianceStatus), nullable=False)
    content = Column(JSON, nullable=False)
    summary = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_regulatory_reports_user_id", "user_id"),
        Index("idx_regulatory_reports_type", "report_type"),
        Index("idx_regulatory_reports_body", "regulatory_body"),
        Index("idx_regulatory_reports_status", "status"),
        Index("idx_regulatory_reports_period", "period_start", "period_end"),
        Index("idx_regulatory_reports_created_at", "created_at"),
    )


class ComplianceRequirementModel(Base):
    """Modèle d'exigence de conformité."""
    __tablename__ = "compliance_requirements"

    requirement_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    compliance_type = Column(SQLEnum(ComplianceType), nullable=False)
    regulatory_body = Column(SQLEnum(RegulatoryBody), nullable=False)
    status = Column(SQLEnum(ComplianceStatus), nullable=False)
    deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_compliance_requirements_user_id", "user_id"),
        Index("idx_compliance_requirements_type", "compliance_type"),
        Index("idx_compliance_requirements_body", "regulatory_body"),
        Index("idx_compliance_requirements_status", "status"),
        Index("idx_compliance_requirements_deadline", "deadline"),
    )


class ComplianceViolationModel(Base):
    """Modèle de violation de conformité."""
    __tablename__ = "compliance_violations"

    violation_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    requirement_id = Column(String(36), ForeignKey("compliance_requirements.requirement_id"), nullable=True)
    report_id = Column(String(36), ForeignKey("regulatory_reports.report_id"), nullable=True)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)
    status = Column(SQLEnum(ComplianceStatus), nullable=False)
    resolution = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_compliance_violations_user_id", "user_id"),
        Index("idx_compliance_violations_requirement_id", "requirement_id"),
        Index("idx_compliance_violations_status", "status"),
        Index("idx_compliance_violations_created_at", "created_at"),
    )


class RegulatoryDocumentModel(Base):
    """Modèle de document réglementaire."""
    __tablename__ = "regulatory_documents"

    document_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    regulatory_body = Column(SQLEnum(RegulatoryBody), nullable=False)
    version = Column(String(20), nullable=False)
    content = Column(JSON, nullable=True)
    file_path = Column(String(500), nullable=True)
    checksum = Column(String(64), nullable=True)
    effective_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_regulatory_documents_user_id", "user_id"),
        Index("idx_regulatory_documents_body", "regulatory_body"),
        Index("idx_regulatory_documents_type", "type"),
        Index("idx_regulatory_documents_effective_date", "effective_date"),
    )


class RegulatoryMetricsModel(Base):
    """Modèle de métriques réglementaires."""
    __tablename__ = "regulatory_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    regulatory_body = Column(SQLEnum(RegulatoryBody), nullable=False)
    compliance_score = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    violations_count = Column(Integer, nullable=False)
    open_requirements = Column(Integer, nullable=False)
    closed_requirements = Column(Integer, nullable=False)
    total_requirements = Column(Integer, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_regulatory_metrics_user_id", "user_id"),
        Index("idx_regulatory_metrics_body", "regulatory_body"),
        Index("idx_regulatory_metrics_calculated_at", "calculated_at"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class RegulatoryReport:
    """Rapport réglementaire."""
    report_id: UUID
    user_id: UUID
    report_type: ReportType
    regulatory_body: RegulatoryBody
    period_start: datetime
    period_end: datetime
    status: ComplianceStatus
    content: Dict[str, Any]
    summary: Optional[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "report_id": str(self.report_id),
            "user_id": str(self.user_id),
            "report_type": self.report_type.value,
            "regulatory_body": self.regulatory_body.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "status": self.status.value,
            "content": self.content,
            "summary": self.summary,
            "metadata": self.metadata,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class ComplianceRequirement:
    """Exigence de conformité."""
    requirement_id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    compliance_type: ComplianceType
    regulatory_body: RegulatoryBody
    status: ComplianceStatus
    deadline: Optional[datetime]
    completed_at: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "requirement_id": str(self.requirement_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "description": self.description,
            "compliance_type": self.compliance_type.value,
            "regulatory_body": self.regulatory_body.value,
            "status": self.status.value,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class ComplianceViolation:
    """Violation de conformité."""
    violation_id: UUID
    user_id: UUID
    requirement_id: Optional[UUID]
    report_id: Optional[UUID]
    description: str
    severity: str
    status: ComplianceStatus
    resolution: Optional[str]
    resolved_at: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "violation_id": str(self.violation_id),
            "user_id": str(self.user_id),
            "requirement_id": str(self.requirement_id) if self.requirement_id else None,
            "report_id": str(self.report_id) if self.report_id else None,
            "description": self.description,
            "severity": self.severity,
            "status": self.status.value,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class RegulatoryDocument:
    """Document réglementaire."""
    document_id: UUID
    user_id: UUID
    name: str
    type: str
    regulatory_body: RegulatoryBody
    version: str
    content: Optional[Dict[str, Any]]
    file_path: Optional[str]
    checksum: Optional[str]
    effective_date: Optional[datetime]
    expiry_date: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)
    uploaded_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "document_id": str(self.document_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "type": self.type,
            "regulatory_body": self.regulatory_body.value,
            "version": self.version,
            "content": self.content,
            "file_path": self.file_path,
            "checksum": self.checksum,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "metadata": self.metadata,
            "uploaded_at": self.uploaded_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class RegulatoryMetrics:
    """Métriques réglementaires."""
    metric_id: UUID
    user_id: UUID
    regulatory_body: RegulatoryBody
    compliance_score: float
    risk_score: float
    violations_count: int
    open_requirements: int
    closed_requirements: int
    total_requirements: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "regulatory_body": self.regulatory_body.value,
            "compliance_score": self.compliance_score,
            "risk_score": self.risk_score,
            "violations_count": self.violations_count,
            "open_requirements": self.open_requirements,
            "closed_requirements": self.closed_requirements,
            "total_requirements": self.total_requirements,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_regulatory_report(
    user_id: UUID,
    report_type: ReportType,
    regulatory_body: RegulatoryBody,
    period_start: datetime,
    period_end: datetime,
    content: Dict[str, Any],
    status: ComplianceStatus = ComplianceStatus.PENDING,
    summary: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict] = None
) -> RegulatoryReport:
    """
    Crée un rapport réglementaire.

    Args:
        user_id: ID de l'utilisateur
        report_type: Type de rapport
        regulatory_body: Autorité réglementaire
        period_start: Date de début
        period_end: Date de fin
        content: Contenu du rapport
        status: Statut
        summary: Résumé
        metadata: Métadonnées

    Returns:
        Rapport réglementaire
    """
    return RegulatoryReport(
        report_id=uuid4(),
        user_id=user_id,
        report_type=report_type,
        regulatory_body=regulatory_body,
        period_start=period_start,
        period_end=period_end,
        status=status,
        content=content,
        summary=summary,
        metadata=metadata or {}
    )


def create_compliance_requirement(
    user_id: UUID,
    name: str,
    compliance_type: ComplianceType,
    regulatory_body: RegulatoryBody,
    status: ComplianceStatus = ComplianceStatus.PENDING,
    description: Optional[str] = None,
    deadline: Optional[datetime] = None,
    metadata: Optional[Dict] = None
) -> ComplianceRequirement:
    """
    Crée une exigence de conformité.

    Args:
        user_id: ID de l'utilisateur
        name: Nom
        compliance_type: Type de conformité
        regulatory_body: Autorité réglementaire
        status: Statut
        description: Description
        deadline: Date limite
        metadata: Métadonnées

    Returns:
        Exigence de conformité
    """
    return ComplianceRequirement(
        requirement_id=uuid4(),
        user_id=user_id,
        name=name,
        description=description,
        compliance_type=compliance_type,
        regulatory_body=regulatory_body,
        status=status,
        deadline=deadline,
        completed_at=None,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "RegulatoryBody",
    "ComplianceType",
    "ComplianceStatus",
    "ReportType",
    "RegulatoryReportModel",
    "ComplianceRequirementModel",
    "ComplianceViolationModel",
    "RegulatoryDocumentModel",
    "RegulatoryMetricsModel",
    "RegulatoryReport",
    "ComplianceRequirement",
    "ComplianceViolation",
    "RegulatoryDocument",
    "RegulatoryMetrics",
    "create_regulatory_report",
    "create_compliance_requirement"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles réglementaires."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT REGULATORY MODELS")
    print("=" * 60)

    # Création d'un rapport réglementaire
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Création d'un rapport réglementaire...")
    
    report = create_regulatory_report(
        user_id=user_id,
        report_type=ReportType.REGULATORY,
        regulatory_body=RegulatoryBody.SEC,
        period_start=datetime.now() - timedelta(days=30),
        period_end=datetime.now(),
        content={
            "trades": 150,
            "volume": 1250000,
            "compliance": "pass"
        },
        status=ComplianceStatus.PENDING,
        summary={"total_trades": 150, "total_volume": 1250000}
    )

    print(f"   ID: {report.report_id}")
    print(f"   Type: {report.report_type.value}")
    print(f"   Autorité: {report.regulatory_body.value}")
    print(f"   Statut: {report.status.value}")
    print(f"   Trades: {report.content['trades']}")

    # Création d'une exigence de conformité
    print(f"\n📋 Création d'une exigence de conformité...")
    
    requirement = create_compliance_requirement(
        user_id=user_id,
        name="KYC Verification",
        compliance_type=ComplianceType.KYC,
        regulatory_body=RegulatoryBody.FATF,
        status=ComplianceStatus.IN_PROGRESS,
        description="Vérification KYC complète des utilisateurs",
        deadline=datetime.now() + timedelta(days=30)
    )

    print(f"   ID: {requirement.requirement_id}")
    print(f"   Nom: {requirement.name}")
    print(f"   Type: {requirement.compliance_type.value}")
    print(f"   Date limite: {requirement.deadline}")

    # Création d'une violation
    print(f"\n⚠️ Création d'une violation de conformité...")
    
    violation = ComplianceViolation(
        violation_id=uuid4(),
        user_id=user_id,
        requirement_id=requirement.requirement_id,
        description="KYC non vérifié pour 5 utilisateurs",
        severity="high",
        status=ComplianceStatus.UNDER_REVIEW,
        resolution=None,
        resolved_at=None
    )

    print(f"   ID: {violation.violation_id}")
    print(f"   Description: {violation.description}")
    print(f"   Sévérité: {violation.severity}")

    # Métriques réglementaires
    print(f"\n📈 Métriques réglementaires:")
    
    metrics = RegulatoryMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        regulatory_body=RegulatoryBody.SEC,
        compliance_score=85.5,
        risk_score=12.3,
        violations_count=2,
        open_requirements=3,
        closed_requirements=7,
        total_requirements=10
    )

    print(f"   Score de conformité: {metrics.compliance_score:.1f}%")
    print(f"   Score de risque: {metrics.risk_score:.1f}%")
    print(f"   Violations: {metrics.violations_count}")
    print(f"   Exigences ouvertes: {metrics.open_requirements}")

    print("\n" + "=" * 60)
    print("Regulatory Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
