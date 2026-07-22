"""
NEXUS AI TRADING SYSTEM - HEDGE BOT RECOVERY MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de récupération pour le Hedge Bot.
Définition des entités de récupération, plans, actions, et métriques.

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

class RecoveryType(Enum):
    """Types de récupération."""
    DRAWDOWN = "drawdown"
    LOSS = "loss"
    LIQUIDATION = "liquidation"
    SYSTEM = "system"
    NETWORK = "network"
    DATA = "data"
    SECURITY = "security"
    OPERATIONAL = "operational"


class RecoveryStatus(Enum):
    """Statuts de récupération."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    MONITORING = "monitoring"


class RecoveryPriority(Enum):
    """Priorités de récupération."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecoveryActionType(Enum):
    """Types d'actions de récupération."""
    REDUCE_POSITION = "reduce_position"
    CLOSE_POSITION = "close_position"
    ADD_COLLATERAL = "add_collateral"
    HEDGE = "hedge"
    REBALANCE = "rebalance"
    STOP_TRADING = "stop_trading"
    ALERT = "alert"
    REPORT = "report"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class RecoveryPlanModel(Base):
    """Modèle de plan de récupération."""
    __tablename__ = "recovery_plans"

    plan_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    recovery_type = Column(SQLEnum(RecoveryType), nullable=False)
    status = Column(SQLEnum(RecoveryStatus), nullable=False)
    priority = Column(SQLEnum(RecoveryPriority), nullable=False)
    trigger_condition = Column(JSON, nullable=False)
    actions = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_recovery_plans_user_id", "user_id"),
        Index("idx_recovery_plans_status", "status"),
        Index("idx_recovery_plans_type", "recovery_type"),
        Index("idx_recovery_plans_created_at", "created_at"),
    )


class RecoveryExecutionModel(Base):
    """Modèle d'exécution de récupération."""
    __tablename__ = "recovery_executions"

    execution_id = Column(String(36), primary_key=True)
    plan_id = Column(String(36), ForeignKey("recovery_plans.plan_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    status = Column(SQLEnum(RecoveryStatus), nullable=False)
    action_type = Column(SQLEnum(RecoveryActionType), nullable=False)
    action_params = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)

    # Relations
    plan = relationship("RecoveryPlanModel")

    __table_args__ = (
        Index("idx_recovery_executions_plan_id", "plan_id"),
        Index("idx_recovery_executions_user_id", "user_id"),
        Index("idx_recovery_executions_status", "status"),
        Index("idx_recovery_executions_started_at", "started_at"),
    )


class RecoveryMetricsModel(Base):
    """Modèle de métriques de récupération."""
    __tablename__ = "recovery_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    recovery_type = Column(SQLEnum(RecoveryType), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    recovery_amount = Column(Numeric(20, 8), nullable=False)
    recovery_percent = Column(Float, nullable=False)
    recovery_time_days = Column(Integer, nullable=False)
    success_rate = Column(Float, nullable=False)
    total_attempts = Column(Integer, nullable=False)
    successful_attempts = Column(Integer, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_recovery_metrics_user_id", "user_id"),
        Index("idx_recovery_metrics_type", "recovery_type"),
        Index("idx_recovery_metrics_period", "period_start", "period_end"),
    )


class RecoveryTriggerModel(Base):
    """Modèle de déclencheur de récupération."""
    __tablename__ = "recovery_triggers"

    trigger_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    condition = Column(JSON, nullable=False)
    recovery_type = Column(SQLEnum(RecoveryType), nullable=False)
    priority = Column(SQLEnum(RecoveryPriority), nullable=False)
    enabled = Column(Boolean, default=True)
    last_triggered = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_recovery_triggers_user_id", "user_id"),
        Index("idx_recovery_triggers_enabled", "enabled"),
        Index("idx_recovery_triggers_type", "recovery_type"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class RecoveryPlan:
    """Plan de récupération."""
    plan_id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    recovery_type: RecoveryType
    status: RecoveryStatus
    priority: RecoveryPriority
    trigger_condition: Dict[str, Any]
    actions: List[Dict[str, Any]]
    metrics: Optional[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    activated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "plan_id": str(self.plan_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "description": self.description,
            "recovery_type": self.recovery_type.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "trigger_condition": self.trigger_condition,
            "actions": self.actions,
            "metrics": self.metrics,
            "metadata": self.metadata,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class RecoveryExecution:
    """Exécution de récupération."""
    execution_id: UUID
    plan_id: UUID
    user_id: UUID
    status: RecoveryStatus
    action_type: RecoveryActionType
    action_params: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "execution_id": str(self.execution_id),
            "plan_id": str(self.plan_id),
            "user_id": str(self.user_id),
            "status": self.status.value,
            "action_type": self.action_type.value,
            "action_params": self.action_params,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class RecoveryMetrics:
    """Métriques de récupération."""
    metric_id: UUID
    user_id: UUID
    recovery_type: RecoveryType
    period_start: datetime
    period_end: datetime
    recovery_amount: Decimal
    recovery_percent: float
    recovery_time_days: int
    success_rate: float
    total_attempts: int
    successful_attempts: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "recovery_type": self.recovery_type.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "recovery_amount": str(self.recovery_amount),
            "recovery_percent": self.recovery_percent,
            "recovery_time_days": self.recovery_time_days,
            "success_rate": self.success_rate,
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class RecoveryTrigger:
    """Déclencheur de récupération."""
    trigger_id: UUID
    user_id: UUID
    name: str
    condition: Dict[str, Any]
    recovery_type: RecoveryType
    priority: RecoveryPriority
    enabled: bool
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "trigger_id": str(self.trigger_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "condition": self.condition,
            "recovery_type": self.recovery_type.value,
            "priority": self.priority.value,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "trigger_count": self.trigger_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_recovery_plan(
    user_id: UUID,
    name: str,
    recovery_type: RecoveryType,
    trigger_condition: Dict[str, Any],
    actions: List[Dict[str, Any]],
    description: Optional[str] = None,
    priority: RecoveryPriority = RecoveryPriority.MEDIUM,
    status: RecoveryStatus = RecoveryStatus.PLANNED,
    metrics: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict] = None
) -> RecoveryPlan:
    """
    Crée un plan de récupération.

    Args:
        user_id: ID de l'utilisateur
        name: Nom du plan
        recovery_type: Type de récupération
        trigger_condition: Condition de déclenchement
        actions: Actions à exécuter
        description: Description
        priority: Priorité
        status: Statut
        metrics: Métriques
        metadata: Métadonnées

    Returns:
        Plan de récupération
    """
    return RecoveryPlan(
        plan_id=uuid4(),
        user_id=user_id,
        name=name,
        description=description,
        recovery_type=recovery_type,
        status=status,
        priority=priority,
        trigger_condition=trigger_condition,
        actions=actions,
        metrics=metrics,
        metadata=metadata or {}
    )


def create_recovery_metrics(
    user_id: UUID,
    recovery_type: RecoveryType,
    period_start: datetime,
    period_end: datetime,
    recovery_amount: Decimal,
    recovery_percent: float,
    recovery_time_days: int,
    success_rate: float,
    total_attempts: int,
    successful_attempts: int,
    metadata: Optional[Dict] = None
) -> RecoveryMetrics:
    """
    Crée des métriques de récupération.

    Args:
        user_id: ID de l'utilisateur
        recovery_type: Type de récupération
        period_start: Date de début
        period_end: Date de fin
        recovery_amount: Montant récupéré
        recovery_percent: Pourcentage récupéré
        recovery_time_days: Temps de récupération
        success_rate: Taux de succès
        total_attempts: Tentatives totales
        successful_attempts: Tentatives réussies
        metadata: Métadonnées

    Returns:
        Métriques de récupération
    """
    return RecoveryMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        recovery_type=recovery_type,
        period_start=period_start,
        period_end=period_end,
        recovery_amount=recovery_amount,
        recovery_percent=recovery_percent,
        recovery_time_days=recovery_time_days,
        success_rate=success_rate,
        total_attempts=total_attempts,
        successful_attempts=successful_attempts,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "RecoveryType",
    "RecoveryStatus",
    "RecoveryPriority",
    "RecoveryActionType",
    "RecoveryPlanModel",
    "RecoveryExecutionModel",
    "RecoveryMetricsModel",
    "RecoveryTriggerModel",
    "RecoveryPlan",
    "RecoveryExecution",
    "RecoveryMetrics",
    "RecoveryTrigger",
    "create_recovery_plan",
    "create_recovery_metrics"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de récupération."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT RECOVERY MODELS")
    print("=" * 60)

    # Création d'un plan de récupération
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📋 Création d'un plan de récupération...")
    
    plan = create_recovery_plan(
        user_id=user_id,
        name="Drawdown Recovery Plan",
        recovery_type=RecoveryType.DRAWDOWN,
        trigger_condition={
            "metric": "drawdown",
            "threshold": 0.10,
            "operator": ">="
        },
        actions=[
            {"type": "reduce_position", "params": {"percentage": 50}},
            {"type": "hedge", "params": {"ratio": 0.75}},
            {"type": "alert", "params": {"level": "warning"}}
        ],
        description="Plan de récupération en cas de drawdown",
        priority=RecoveryPriority.HIGH
    )

    print(f"   ID: {plan.plan_id}")
    print(f"   Nom: {plan.name}")
    print(f"   Type: {plan.recovery_type.value}")
    print(f"   Priorité: {plan.priority.value}")
    print(f"   Actions: {len(plan.actions)}")

    # Création d'une exécution
    print(f"\n⚡ Création d'une exécution de récupération...")
    
    execution = RecoveryExecution(
        execution_id=uuid4(),
        plan_id=plan.plan_id,
        user_id=user_id,
        status=RecoveryStatus.IN_PROGRESS,
        action_type=RecoveryActionType.REDUCE_POSITION,
        action_params={"percentage": 50},
        result={"position_reduced": True},
        error=None,
        started_at=datetime.now()
    )

    print(f"   ID: {execution.execution_id}")
    print(f"   Action: {execution.action_type.value}")
    print(f"   Statut: {execution.status.value}")
    print(f"   Résultat: {execution.result}")

    # Métriques de récupération
    print(f"\n📊 Métriques de récupération:")
    
    metrics = create_recovery_metrics(
        user_id=user_id,
        recovery_type=RecoveryType.DRAWDOWN,
        period_start=datetime.now() - timedelta(days=30),
        period_end=datetime.now(),
        recovery_amount=Decimal("5000"),
        recovery_percent=85.5,
        recovery_time_days=15,
        success_rate=0.75,
        total_attempts=4,
        successful_attempts=3
    )

    print(f"   Montant récupéré: ${metrics.recovery_amount}")
    print(f"   Pourcentage: {metrics.recovery_percent:.1f}%")
    print(f"   Temps: {metrics.recovery_time_days} jours")
    print(f"   Taux de succès: {metrics.success_rate*100:.1f}%")

    # Déclencheur
    print(f"\n🔔 Création d'un déclencheur de récupération...")
    
    trigger = RecoveryTrigger(
        trigger_id=uuid4(),
        user_id=user_id,
        name="Drawdown Trigger",
        condition={
            "metric": "drawdown",
            "threshold": 0.10,
            "operator": ">="
        },
        recovery_type=RecoveryType.DRAWDOWN,
        priority=RecoveryPriority.HIGH,
        enabled=True,
        trigger_count=0
    )

    print(f"   ID: {trigger.trigger_id}")
    print(f"   Nom: {trigger.name}")
    print(f"   Condition: {trigger.condition}")
    print(f"   Actif: {trigger.enabled}")

    print("\n" + "=" * 60)
    print("Recovery Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
