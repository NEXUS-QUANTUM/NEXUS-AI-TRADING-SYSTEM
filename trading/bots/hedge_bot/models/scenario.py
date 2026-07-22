"""
NEXUS AI TRADING SYSTEM - HEDGE BOT SCENARIO MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de scénarios pour le Hedge Bot.
Définition des entités de scénarios, simulations, et métriques associées.

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

class ScenarioType(Enum):
    """Types de scénarios."""
    MARKET = "market"
    STRESS = "stress"
    HISTORICAL = "historical"
    MONTE_CARLO = "monte_carlo"
    WHAT_IF = "what_if"
    WORST_CASE = "worst_case"
    BEST_CASE = "best_case"
    BLACK_SWAN = "black_swan"


class ScenarioStatus(Enum):
    """Statuts de scénario."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScenarioSeverity(Enum):
    """Sévérités de scénario."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SEVERE = "severe"
    CATASTROPHIC = "catastrophic"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class ScenarioModel(Base):
    """Modèle de scénario."""
    __tablename__ = "scenarios"

    scenario_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scenario_type = Column(SQLEnum(ScenarioType), nullable=False)
    status = Column(SQLEnum(ScenarioStatus), nullable=False)
    severity = Column(SQLEnum(ScenarioSeverity), nullable=True)
    parameters = Column(JSON, nullable=False)
    assumptions = Column(JSON, nullable=True)
    results = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_scenarios_user_id", "user_id"),
        Index("idx_scenarios_type", "scenario_type"),
        Index("idx_scenarios_status", "status"),
        Index("idx_scenarios_severity", "severity"),
        Index("idx_scenarios_created_at", "created_at"),
    )


class ScenarioSimulationModel(Base):
    """Modèle de simulation de scénario."""
    __tablename__ = "scenario_simulations"

    simulation_id = Column(String(36), primary_key=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.scenario_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    iteration = Column(Integer, nullable=False)
    variables = Column(JSON, nullable=False)
    outcomes = Column(JSON, nullable=False)
    probability = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    executed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    scenario = relationship("ScenarioModel")

    __table_args__ = (
        Index("idx_scenario_simulations_scenario_id", "scenario_id"),
        Index("idx_scenario_simulations_user_id", "user_id"),
        Index("idx_scenario_simulations_iteration", "iteration"),
        Index("idx_scenario_simulations_executed_at", "executed_at"),
    )


class ScenarioImpactModel(Base):
    """Modèle d'impact de scénario."""
    __tablename__ = "scenario_impacts"

    impact_id = Column(String(36), primary_key=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.scenario_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    asset = Column(String(50), nullable=False)
    impact_percent = Column(Float, nullable=False)
    impact_value = Column(Numeric(20, 8), nullable=False)
    recovery_time_days = Column(Integer, nullable=True)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    scenario = relationship("ScenarioModel")

    __table_args__ = (
        Index("idx_scenario_impacts_scenario_id", "scenario_id"),
        Index("idx_scenario_impacts_user_id", "user_id"),
        Index("idx_scenario_impacts_asset", "asset"),
    )


class ScenarioMetricsModel(Base):
    """Modèle de métriques de scénario."""
    __tablename__ = "scenario_metrics"

    metric_id = Column(String(36), primary_key=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.scenario_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    total_loss = Column(Numeric(20, 8), nullable=False)
    max_loss = Column(Numeric(20, 8), nullable=False)
    avg_loss = Column(Numeric(20, 8), nullable=False)
    recovery_rate = Column(Float, nullable=False)
    volatility_impact = Column(Float, nullable=False)
    correlation_shift = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    scenario = relationship("ScenarioModel")

    __table_args__ = (
        Index("idx_scenario_metrics_scenario_id", "scenario_id"),
        Index("idx_scenario_metrics_user_id", "user_id"),
        Index("idx_scenario_metrics_calculated_at", "calculated_at"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class Scenario:
    """Scénario."""
    scenario_id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    scenario_type: ScenarioType
    status: ScenarioStatus
    severity: Optional[ScenarioSeverity]
    parameters: Dict[str, Any]
    assumptions: Optional[Dict[str, Any]]
    results: Optional[Dict[str, Any]]
    metrics: Optional[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "scenario_id": str(self.scenario_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "description": self.description,
            "scenario_type": self.scenario_type.value,
            "status": self.status.value,
            "severity": self.severity.value if self.severity else None,
            "parameters": self.parameters,
            "assumptions": self.assumptions,
            "results": self.results,
            "metrics": self.metrics,
            "metadata": self.metadata,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class ScenarioSimulation:
    """Simulation de scénario."""
    simulation_id: UUID
    scenario_id: UUID
    user_id: UUID
    iteration: int
    variables: Dict[str, Any]
    outcomes: Dict[str, Any]
    probability: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    executed_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "simulation_id": str(self.simulation_id),
            "scenario_id": str(self.scenario_id),
            "user_id": str(self.user_id),
            "iteration": self.iteration,
            "variables": self.variables,
            "outcomes": self.outcomes,
            "probability": self.probability,
            "metadata": self.metadata,
            "executed_at": self.executed_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ScenarioImpact:
    """Impact de scénario."""
    impact_id: UUID
    scenario_id: UUID
    user_id: UUID
    asset: str
    impact_percent: float
    impact_value: Decimal
    recovery_time_days: Optional[int]
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "impact_id": str(self.impact_id),
            "scenario_id": str(self.scenario_id),
            "user_id": str(self.user_id),
            "asset": self.asset,
            "impact_percent": self.impact_percent,
            "impact_value": str(self.impact_value),
            "recovery_time_days": self.recovery_time_days,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ScenarioMetrics:
    """Métriques de scénario."""
    metric_id: UUID
    scenario_id: UUID
    user_id: UUID
    total_loss: Decimal
    max_loss: Decimal
    avg_loss: Decimal
    recovery_rate: float
    volatility_impact: float
    correlation_shift: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "scenario_id": str(self.scenario_id),
            "user_id": str(self.user_id),
            "total_loss": str(self.total_loss),
            "max_loss": str(self.max_loss),
            "avg_loss": str(self.avg_loss),
            "recovery_rate": self.recovery_rate,
            "volatility_impact": self.volatility_impact,
            "correlation_shift": self.correlation_shift,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_scenario(
    user_id: UUID,
    name: str,
    scenario_type: ScenarioType,
    parameters: Dict[str, Any],
    description: Optional[str] = None,
    assumptions: Optional[Dict[str, Any]] = None,
    severity: Optional[ScenarioSeverity] = None,
    status: ScenarioStatus = ScenarioStatus.PENDING,
    metadata: Optional[Dict] = None
) -> Scenario:
    """
    Crée un scénario.

    Args:
        user_id: ID de l'utilisateur
        name: Nom du scénario
        scenario_type: Type de scénario
        parameters: Paramètres
        description: Description
        assumptions: Hypothèses
        severity: Sévérité
        status: Statut
        metadata: Métadonnées

    Returns:
        Scénario créé
    """
    return Scenario(
        scenario_id=uuid4(),
        user_id=user_id,
        name=name,
        description=description,
        scenario_type=scenario_type,
        status=status,
        severity=severity,
        parameters=parameters,
        assumptions=assumptions,
        results=None,
        metrics=None,
        metadata=metadata or {}
    )


def create_scenario_impact(
    scenario_id: UUID,
    user_id: UUID,
    asset: str,
    impact_percent: float,
    impact_value: Decimal,
    recovery_time_days: Optional[int] = None,
    metadata: Optional[Dict] = None
) -> ScenarioImpact:
    """
    Crée un impact de scénario.

    Args:
        scenario_id: ID du scénario
        user_id: ID de l'utilisateur
        asset: Actif
        impact_percent: Pourcentage d'impact
        impact_value: Valeur d'impact
        recovery_time_days: Temps de récupération
        metadata: Métadonnées

    Returns:
        Impact de scénario
    """
    return ScenarioImpact(
        impact_id=uuid4(),
        scenario_id=scenario_id,
        user_id=user_id,
        asset=asset,
        impact_percent=impact_percent,
        impact_value=impact_value,
        recovery_time_days=recovery_time_days,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ScenarioType",
    "ScenarioStatus",
    "ScenarioSeverity",
    "ScenarioModel",
    "ScenarioSimulationModel",
    "ScenarioImpactModel",
    "ScenarioMetricsModel",
    "Scenario",
    "ScenarioSimulation",
    "ScenarioImpact",
    "ScenarioMetrics",
    "create_scenario",
    "create_scenario_impact"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de scénarios."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT SCENARIO MODELS")
    print("=" * 60)

    # Création d'un scénario
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Création d'un scénario...")
    
    scenario = create_scenario(
        user_id=user_id,
        name="Flash Crash BTC",
        scenario_type=ScenarioType.STRESS,
        parameters={
            "price_drop": 0.30,
            "duration_minutes": 15,
            "recovery_days": 7
        },
        description="Scénario de flash crash sur Bitcoin",
        assumptions={"liquidity": "normal", "volatility": "high"},
        severity=ScenarioSeverity.SEVERE,
        metadata={"source": "stress_test"}
    )

    print(f"   ID: {scenario.scenario_id}")
    print(f"   Nom: {scenario.name}")
    print(f"   Type: {scenario.scenario_type.value}")
    print(f"   Sévérité: {scenario.severity.value}")
    print(f"   Paramètres: {scenario.parameters}")

    # Création d'une simulation
    print(f"\n🔄 Création d'une simulation...")
    
    simulation = ScenarioSimulation(
        simulation_id=uuid4(),
        scenario_id=scenario.scenario_id,
        user_id=user_id,
        iteration=1,
        variables={
            "btc_price": 50000,
            "eth_price": 3000,
            "volatility": 0.35
        },
        outcomes={
            "btc_final": 35000,
            "eth_final": 2100,
            "loss_percent": 0.30,
            "recovery_days": 7
        },
        probability=0.05
    )

    print(f"   ID: {simulation.simulation_id}")
    print(f"   Itération: {simulation.iteration}")
    print(f"   Probabilité: {simulation.probability:.1%}")
    print(f"   Variables: {simulation.variables}")

    # Création d'un impact
    print(f"\n📈 Création d'un impact...")
    
    impact = create_scenario_impact(
        scenario_id=scenario.scenario_id,
        user_id=user_id,
        asset="BTC/USDT",
        impact_percent=-0.30,
        impact_value=Decimal("-15000"),
        recovery_time_days=7,
        metadata={"position": "long"}
    )

    print(f"   ID: {impact.impact_id}")
    print(f"   Actif: {impact.asset}")
    print(f"   Impact: {impact.impact_percent:.1%}")
    print(f"   Valeur: ${impact.impact_value}")
    print(f"   Récupération: {impact.recovery_time_days} jours")

    # Métriques
    print(f"\n📊 Métriques du scénario:")
    
    metrics = ScenarioMetrics(
        metric_id=uuid4(),
        scenario_id=scenario.scenario_id,
        user_id=user_id,
        total_loss=Decimal("25000"),
        max_loss=Decimal("15000"),
        avg_loss=Decimal("12500"),
        recovery_rate=0.85,
        volatility_impact=0.42,
        correlation_shift=0.15
    )

    print(f"   Perte totale: ${metrics.total_loss}")
    print(f"   Perte max: ${metrics.max_loss}")
    print(f"   Taux de récupération: {metrics.recovery_rate:.1%}")
    print(f"   Impact volatilité: {metrics.volatility_impact:.1%}")

    print("\n" + "=" * 60)
    print("Scenario Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
