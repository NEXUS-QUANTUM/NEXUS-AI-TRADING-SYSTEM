"""
NEXUS AI TRADING SYSTEM - HEDGE BOT RISK MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de risque pour le Hedge Bot.
Définition des entités de risque, métriques, évaluations, et limites.

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

import numpy as np
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

class RiskType(Enum):
    """Types de risques."""
    MARKET = "market"
    LIQUIDITY = "liquidity"
    COUNTERPARTY = "counterparty"
    OPERATIONAL = "operational"
    SYSTEMIC = "systemic"
    REGULATORY = "regulatory"
    TECHNICAL = "technical"
    EXECUTION = "execution"
    SLIPPAGE = "slippage"
    GAS = "gas"
    BRIDGE = "bridge"
    SMART_CONTRACT = "smart_contract"
    CONCENTRATION = "concentration"
    VOLATILITY = "volatility"


class RiskLevel(Enum):
    """Niveaux de risque."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"


class RiskStatus(Enum):
    """Statuts de risque."""
    PENDING = "pending"
    ACTIVE = "active"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    TRANSFERRED = "transferred"
    ESCALATED = "escalated"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class RiskAssessmentModel(Base):
    """Modèle d'évaluation des risques."""
    __tablename__ = "risk_assessments"

    assessment_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=True)
    risk_type = Column(SQLEnum(RiskType), nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    status = Column(SQLEnum(RiskStatus), nullable=False)
    score = Column(Float, nullable=False)
    probability = Column(Float, nullable=False)
    impact = Column(Float, nullable=False)
    severity = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    mitigation_plan = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    assessed_at = Column(DateTime, nullable=False)
    mitigated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_risk_assessments_user_id", "user_id"),
        Index("idx_risk_assessments_position_id", "position_id"),
        Index("idx_risk_assessments_type", "risk_type"),
        Index("idx_risk_assessments_level", "risk_level"),
        Index("idx_risk_assessments_status", "status"),
        Index("idx_risk_assessments_assessed_at", "assessed_at"),
    )


class RiskMetricsModel(Base):
    """Modèle de métriques de risque."""
    __tablename__ = "risk_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=True)
    total_risk_score = Column(Float, nullable=False)
    max_drawdown = Column(Float, nullable=False)
    current_drawdown = Column(Float, nullable=False)
    volatility = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=False)
    sortino_ratio = Column(Float, nullable=False)
    calmar_ratio = Column(Float, nullable=False)
    var_95 = Column(Numeric(20, 8), nullable=False)
    var_99 = Column(Numeric(20, 8), nullable=False)
    expected_shortfall = Column(Numeric(20, 8), nullable=False)
    beta = Column(Float, nullable=False)
    alpha = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_risk_metrics_user_id", "user_id"),
        Index("idx_risk_metrics_position_id", "position_id"),
        Index("idx_risk_metrics_calculated_at", "calculated_at"),
    )


class RiskLimitModel(Base):
    """Modèle de limite de risque."""
    __tablename__ = "risk_limits"

    limit_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    risk_type = Column(SQLEnum(RiskType), nullable=False)
    metric = Column(String(50), nullable=False)
    max_value = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False)
    threshold_warning = Column(Float, nullable=False)
    threshold_critical = Column(Float, nullable=False)
    action = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_risk_limits_user_id", "user_id"),
        Index("idx_risk_limits_type", "risk_type"),
        Index("idx_risk_limits_metric", "metric"),
        Index("idx_risk_limits_enabled", "enabled"),
    )


class RiskEventModel(Base):
    """Modèle d'événement de risque."""
    __tablename__ = "risk_events"

    event_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    risk_type = Column(SQLEnum(RiskType), nullable=False)
    severity = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    affected_assets = Column(JSON, nullable=True)
    action_taken = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)
    occurred_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_risk_events_user_id", "user_id"),
        Index("idx_risk_events_type", "risk_type"),
        Index("idx_risk_events_severity", "severity"),
        Index("idx_risk_events_occurred_at", "occurred_at"),
    )


class RiskMitigationModel(Base):
    """Modèle de mitigation des risques."""
    __tablename__ = "risk_mitigations"

    mitigation_id = Column(String(36), primary_key=True)
    assessment_id = Column(String(36), ForeignKey("risk_assessments.assessment_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    action = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False)
    effectiveness = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Relations
    assessment = relationship("RiskAssessmentModel")

    __table_args__ = (
        Index("idx_risk_mitigations_assessment_id", "assessment_id"),
        Index("idx_risk_mitigations_user_id", "user_id"),
        Index("idx_risk_mitigations_status", "status"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class RiskAssessment:
    """Évaluation des risques."""
    assessment_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    risk_type: RiskType
    risk_level: RiskLevel
    status: RiskStatus
    score: float
    probability: float
    impact: float
    severity: float
    description: Optional[str]
    mitigation_plan: Optional[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    assessed_at: datetime = field(default_factory=datetime.now)
    mitigated_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "assessment_id": str(self.assessment_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id) if self.position_id else None,
            "risk_type": self.risk_type.value,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "score": self.score,
            "probability": self.probability,
            "impact": self.impact,
            "severity": self.severity,
            "description": self.description,
            "mitigation_plan": self.mitigation_plan,
            "metadata": self.metadata,
            "assessed_at": self.assessed_at.isoformat(),
            "mitigated_at": self.mitigated_at.isoformat() if self.mitigated_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class RiskMetrics:
    """Métriques de risque."""
    metric_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    total_risk_score: float
    max_drawdown: float
    current_drawdown: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    var_95: Decimal
    var_99: Decimal
    expected_shortfall: Decimal
    beta: float
    alpha: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id) if self.position_id else None,
            "total_risk_score": self.total_risk_score,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "var_95": str(self.var_95),
            "var_99": str(self.var_99),
            "expected_shortfall": str(self.expected_shortfall),
            "beta": self.beta,
            "alpha": self.alpha,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class RiskLimit:
    """Limite de risque."""
    limit_id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    risk_type: RiskType
    metric: str
    max_value: float
    current_value: float
    threshold_warning: float
    threshold_critical: float
    action: str
    enabled: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "limit_id": str(self.limit_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "description": self.description,
            "risk_type": self.risk_type.value,
            "metric": self.metric,
            "max_value": self.max_value,
            "current_value": self.current_value,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "action": self.action,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class RiskEvent:
    """Événement de risque."""
    event_id: UUID
    user_id: UUID
    risk_type: RiskType
    severity: str
    description: str
    details: Optional[Dict[str, Any]]
    affected_assets: Optional[List[str]]
    action_taken: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved_at: Optional[datetime] = None
    occurred_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "event_id": str(self.event_id),
            "user_id": str(self.user_id),
            "risk_type": self.risk_type.value,
            "severity": self.severity,
            "description": self.description,
            "details": self.details,
            "affected_assets": self.affected_assets,
            "action_taken": self.action_taken,
            "metadata": self.metadata,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "occurred_at": self.occurred_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class RiskMitigation:
    """Mitigation des risques."""
    mitigation_id: UUID
    assessment_id: UUID
    user_id: UUID
    action: str
    description: Optional[str]
    status: str
    effectiveness: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "mitigation_id": str(self.mitigation_id),
            "assessment_id": str(self.assessment_id),
            "user_id": str(self.user_id),
            "action": self.action,
            "description": self.description,
            "status": self.status,
            "effectiveness": self.effectiveness,
            "metadata": self.metadata,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_risk_assessment(
    user_id: UUID,
    risk_type: RiskType,
    risk_level: RiskLevel,
    score: float,
    probability: float,
    impact: float,
    severity: float,
    position_id: Optional[UUID] = None,
    description: Optional[str] = None,
    mitigation_plan: Optional[Dict[str, Any]] = None,
    status: RiskStatus = RiskStatus.PENDING,
    metadata: Optional[Dict] = None
) -> RiskAssessment:
    """
    Crée une évaluation des risques.

    Args:
        user_id: ID de l'utilisateur
        risk_type: Type de risque
        risk_level: Niveau de risque
        score: Score
        probability: Probabilité
        impact: Impact
        severity: Sévérité
        position_id: ID de la position
        description: Description
        mitigation_plan: Plan de mitigation
        status: Statut
        metadata: Métadonnées

    Returns:
        Évaluation des risques
    """
    return RiskAssessment(
        assessment_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        risk_type=risk_type,
        risk_level=risk_level,
        status=status,
        score=score,
        probability=probability,
        impact=impact,
        severity=severity,
        description=description,
        mitigation_plan=mitigation_plan,
        metadata=metadata or {}
    )


def create_risk_metrics(
    user_id: UUID,
    total_risk_score: float,
    max_drawdown: float,
    current_drawdown: float,
    volatility: float,
    sharpe_ratio: float,
    sortino_ratio: float,
    calmar_ratio: float,
    var_95: Decimal,
    var_99: Decimal,
    expected_shortfall: Decimal,
    beta: float = 1.0,
    alpha: float = 0.0,
    position_id: Optional[UUID] = None,
    metadata: Optional[Dict] = None
) -> RiskMetrics:
    """
    Crée des métriques de risque.

    Args:
        user_id: ID de l'utilisateur
        total_risk_score: Score de risque total
        max_drawdown: Drawdown maximum
        current_drawdown: Drawdown actuel
        volatility: Volatilité
        sharpe_ratio: Sharpe Ratio
        sortino_ratio: Sortino Ratio
        calmar_ratio: Calmar Ratio
        var_95: VaR 95%
        var_99: VaR 99%
        expected_shortfall: Expected Shortfall
        beta: Beta
        alpha: Alpha
        position_id: ID de la position
        metadata: Métadonnées

    Returns:
        Métriques de risque
    """
    return RiskMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        total_risk_score=total_risk_score,
        max_drawdown=max_drawdown,
        current_drawdown=current_drawdown,
        volatility=volatility,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
        var_95=var_95,
        var_99=var_99,
        expected_shortfall=expected_shortfall,
        beta=beta,
        alpha=alpha,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "RiskType",
    "RiskLevel",
    "RiskStatus",
    "RiskAssessmentModel",
    "RiskMetricsModel",
    "RiskLimitModel",
    "RiskEventModel",
    "RiskMitigationModel",
    "RiskAssessment",
    "RiskMetrics",
    "RiskLimit",
    "RiskEvent",
    "RiskMitigation",
    "create_risk_assessment",
    "create_risk_metrics"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de risque."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT RISK MODELS")
    print("=" * 60)

    # Création d'une évaluation des risques
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    position_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'une évaluation des risques...")
    
    assessment = create_risk_assessment(
        user_id=user_id,
        risk_type=RiskType.MARKET,
        risk_level=RiskLevel.HIGH,
        score=75.5,
        probability=0.65,
        impact=0.80,
        severity=0.72,
        position_id=position_id,
        description="Risque de marché élevé dû à la volatilité",
        mitigation_plan={"action": "reduce_position", "percentage": 50},
        status=RiskStatus.ACTIVE,
        metadata={"source": "volatility_analysis"}
    )

    print(f"   ID: {assessment.assessment_id}")
    print(f"   Type: {assessment.risk_type.value}")
    print(f"   Niveau: {assessment.risk_level.value}")
    print(f"   Score: {assessment.score:.1f}")
    print(f"   Probabilité: {assessment.probability:.1%}")
    print(f"   Impact: {assessment.impact:.1%}")

    # Création de métriques de risque
    print(f"\n📈 Métriques de risque...")
    
    metrics = create_risk_metrics(
        user_id=user_id,
        total_risk_score=42.5,
        max_drawdown=0.15,
        current_drawdown=0.08,
        volatility=0.35,
        sharpe_ratio=1.45,
        sortino_ratio=1.20,
        calmar_ratio=0.85,
        var_95=Decimal("15000"),
        var_99=Decimal("25000"),
        expected_shortfall=Decimal("20000"),
        beta=1.2,
        alpha=0.03,
        position_id=position_id
    )

    print(f"   Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"   Sortino Ratio: {metrics.sortino_ratio:.2f}")
    print(f"   Volatilité: {metrics.volatility:.1%}")
    print(f"   VaR 95%: ${metrics.var_95}")

    # Création d'une limite de risque
    print(f"\n🔒 Limite de risque...")
    
    limit = RiskLimit(
        limit_id=uuid4(),
        user_id=user_id,
        name="Max Drawdown Limit",
        description="Limite de drawdown maximum",
        risk_type=RiskType.MARKET,
        metric="max_drawdown",
        max_value=0.20,
        current_value=0.08,
        threshold_warning=0.10,
        threshold_critical=0.15,
        action="stop_trading",
        enabled=True
    )

    print(f"   Nom: {limit.name}")
    print(f"   Valeur max: {limit.max_value:.1%}")
    print(f"   Seuil warning: {limit.threshold_warning:.1%}")

    # Création d'un événement de risque
    print(f"\n⚠️ Événement de risque...")
    
    event = RiskEvent(
        event_id=uuid4(),
        user_id=user_id,
        risk_type=RiskType.SLIPPAGE,
        severity="medium",
        description="Slippage de 0.5% sur l'ordre BTC/USDT",
        details={"expected": 50000, "actual": 49750},
        affected_assets=["BTC/USDT"],
        action_taken="Ajusté la taille de l'ordre",
        occurred_at=datetime.now()
    )

    print(f"   Type: {event.risk_type.value}")
    print(f"   Sévérité: {event.severity}")
    print(f"   Description: {event.description}")

    print("\n" + "=" * 60)
    print("Risk Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
