"""
NEXUS AI TRADING SYSTEM - HEDGE BOT SENSITIVITY MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de sensibilité pour le Hedge Bot.
Définition des entités de sensibilité, analyses, et métriques associées.

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

class SensitivityType(Enum):
    """Types de sensibilité."""
    PRICE = "price"
    VOLATILITY = "volatility"
    RATE = "rate"
    TIME = "time"
    CORRELATION = "correlation"
    GREEK = "greek"
    FACTOR = "factor"
    PARAMETER = "parameter"


class SensitivityLevel(Enum):
    """Niveaux de sensibilité."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class SensitivityStatus(Enum):
    """Statuts de sensibilité."""
    PENDING = "pending"
    CALCULATED = "calculated"
    VERIFIED = "verified"
    UPDATED = "updated"
    ERROR = "error"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class SensitivityAnalysisModel(Base):
    """Modèle d'analyse de sensibilité."""
    __tablename__ = "sensitivity_analyses"

    analysis_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=True)
    symbol = Column(String(50), nullable=False)
    sensitivity_type = Column(SQLEnum(SensitivityType), nullable=False)
    status = Column(SQLEnum(SensitivityStatus), nullable=False)
    level = Column(SQLEnum(SensitivityLevel), nullable=True)
    base_value = Column(Numeric(20, 8), nullable=False)
    sensitivity_value = Column(Float, nullable=False)
    elasticity = Column(Float, nullable=False)
    delta = Column(Float, nullable=False)
    gamma = Column(Float, nullable=True)
    theta = Column(Float, nullable=True)
    vega = Column(Float, nullable=True)
    rho = Column(Float, nullable=True)
    parameters = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_sensitivity_analyses_user_id", "user_id"),
        Index("idx_sensitivity_analyses_position_id", "position_id"),
        Index("idx_sensitivity_analyses_symbol", "symbol"),
        Index("idx_sensitivity_analyses_type", "sensitivity_type"),
        Index("idx_sensitivity_analyses_status", "status"),
        Index("idx_sensitivity_analyses_calculated_at", "calculated_at"),
    )


class SensitivityFactorModel(Base):
    """Modèle de facteur de sensibilité."""
    __tablename__ = "sensitivity_factors"

    factor_id = Column(String(36), primary_key=True)
    analysis_id = Column(String(36), ForeignKey("sensitivity_analyses.analysis_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    factor_type = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    impact = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Relations
    analysis = relationship("SensitivityAnalysisModel")

    __table_args__ = (
        Index("idx_sensitivity_factors_analysis_id", "analysis_id"),
        Index("idx_sensitivity_factors_user_id", "user_id"),
        Index("idx_sensitivity_factors_type", "factor_type"),
    )


class SensitivityScenarioModel(Base):
    """Modèle de scénario de sensibilité."""
    __tablename__ = "sensitivity_scenarios"

    scenario_id = Column(String(36), primary_key=True)
    analysis_id = Column(String(36), ForeignKey("sensitivity_analyses.analysis_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    variables = Column(JSON, nullable=False)
    outcomes = Column(JSON, nullable=False)
    probability = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Relations
    analysis = relationship("SensitivityAnalysisModel")

    __table_args__ = (
        Index("idx_sensitivity_scenarios_analysis_id", "analysis_id"),
        Index("idx_sensitivity_scenarios_user_id", "user_id"),
    )


class SensitivityMetricsModel(Base):
    """Modèle de métriques de sensibilité."""
    __tablename__ = "sensitivity_metrics"

    metric_id = Column(String(36), primary_key=True)
    analysis_id = Column(String(36), ForeignKey("sensitivity_analyses.analysis_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    total_sensitivity = Column(Float, nullable=False)
    average_sensitivity = Column(Float, nullable=False)
    max_sensitivity = Column(Float, nullable=False)
    min_sensitivity = Column(Float, nullable=False)
    sensitivity_ratio = Column(Float, nullable=False)
    factor_count = Column(Integer, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    analysis = relationship("SensitivityAnalysisModel")

    __table_args__ = (
        Index("idx_sensitivity_metrics_analysis_id", "analysis_id"),
        Index("idx_sensitivity_metrics_user_id", "user_id"),
        Index("idx_sensitivity_metrics_calculated_at", "calculated_at"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class SensitivityAnalysis:
    """Analyse de sensibilité."""
    analysis_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    symbol: str
    sensitivity_type: SensitivityType
    status: SensitivityStatus
    level: Optional[SensitivityLevel]
    base_value: Decimal
    sensitivity_value: float
    elasticity: float
    delta: float
    gamma: Optional[float]
    theta: Optional[float]
    vega: Optional[float]
    rho: Optional[float]
    parameters: Optional[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    verified_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "analysis_id": str(self.analysis_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id) if self.position_id else None,
            "symbol": self.symbol,
            "sensitivity_type": self.sensitivity_type.value,
            "status": self.status.value,
            "level": self.level.value if self.level else None,
            "base_value": str(self.base_value),
            "sensitivity_value": self.sensitivity_value,
            "elasticity": self.elasticity,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "parameters": self.parameters,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class SensitivityFactor:
    """Facteur de sensibilité."""
    factor_id: UUID
    analysis_id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    factor_type: str
    value: float
    weight: float
    impact: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "factor_id": str(self.factor_id),
            "analysis_id": str(self.analysis_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "description": self.description,
            "factor_type": self.factor_type,
            "value": self.value,
            "weight": self.weight,
            "impact": self.impact,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class SensitivityScenario:
    """Scénario de sensibilité."""
    scenario_id: UUID
    analysis_id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    variables: Dict[str, Any]
    outcomes: Dict[str, Any]
    probability: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "scenario_id": str(self.scenario_id),
            "analysis_id": str(self.analysis_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "description": self.description,
            "variables": self.variables,
            "outcomes": self.outcomes,
            "probability": self.probability,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class SensitivityMetrics:
    """Métriques de sensibilité."""
    metric_id: UUID
    analysis_id: UUID
    user_id: UUID
    total_sensitivity: float
    average_sensitivity: float
    max_sensitivity: float
    min_sensitivity: float
    sensitivity_ratio: float
    factor_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "analysis_id": str(self.analysis_id),
            "user_id": str(self.user_id),
            "total_sensitivity": self.total_sensitivity,
            "average_sensitivity": self.average_sensitivity,
            "max_sensitivity": self.max_sensitivity,
            "min_sensitivity": self.min_sensitivity,
            "sensitivity_ratio": self.sensitivity_ratio,
            "factor_count": self.factor_count,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_sensitivity_analysis(
    user_id: UUID,
    symbol: str,
    sensitivity_type: SensitivityType,
    base_value: Decimal,
    sensitivity_value: float,
    elasticity: float,
    delta: float,
    position_id: Optional[UUID] = None,
    gamma: Optional[float] = None,
    theta: Optional[float] = None,
    vega: Optional[float] = None,
    rho: Optional[float] = None,
    parameters: Optional[Dict[str, Any]] = None,
    status: SensitivityStatus = SensitivityStatus.PENDING,
    metadata: Optional[Dict] = None
) -> SensitivityAnalysis:
    """
    Crée une analyse de sensibilité.

    Args:
        user_id: ID de l'utilisateur
        symbol: Symbole
        sensitivity_type: Type de sensibilité
        base_value: Valeur de base
        sensitivity_value: Valeur de sensibilité
        elasticity: Élasticité
        delta: Delta
        position_id: ID de la position
        gamma: Gamma
        theta: Theta
        vega: Vega
        rho: Rho
        parameters: Paramètres
        status: Statut
        metadata: Métadonnées

    Returns:
        Analyse de sensibilité
    """
    return SensitivityAnalysis(
        analysis_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        symbol=symbol,
        sensitivity_type=sensitivity_type,
        status=status,
        level=None,
        base_value=base_value,
        sensitivity_value=sensitivity_value,
        elasticity=elasticity,
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        rho=rho,
        parameters=parameters,
        metadata=metadata or {}
    )


def create_sensitivity_factor(
    analysis_id: UUID,
    user_id: UUID,
    name: str,
    factor_type: str,
    value: float,
    weight: float,
    impact: float,
    description: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> SensitivityFactor:
    """
    Crée un facteur de sensibilité.

    Args:
        analysis_id: ID de l'analyse
        user_id: ID de l'utilisateur
        name: Nom
        factor_type: Type de facteur
        value: Valeur
        weight: Poids
        impact: Impact
        description: Description
        metadata: Métadonnées

    Returns:
        Facteur de sensibilité
    """
    return SensitivityFactor(
        factor_id=uuid4(),
        analysis_id=analysis_id,
        user_id=user_id,
        name=name,
        description=description,
        factor_type=factor_type,
        value=value,
        weight=weight,
        impact=impact,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "SensitivityType",
    "SensitivityLevel",
    "SensitivityStatus",
    "SensitivityAnalysisModel",
    "SensitivityFactorModel",
    "SensitivityScenarioModel",
    "SensitivityMetricsModel",
    "SensitivityAnalysis",
    "SensitivityFactor",
    "SensitivityScenario",
    "SensitivityMetrics",
    "create_sensitivity_analysis",
    "create_sensitivity_factor"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de sensibilité."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT SENSITIVITY MODELS")
    print("=" * 60)

    # Création d'une analyse de sensibilité
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    position_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'une analyse de sensibilité...")
    
    analysis = create_sensitivity_analysis(
        user_id=user_id,
        symbol="BTC/USDT",
        sensitivity_type=SensitivityType.PRICE,
        base_value=Decimal("50000"),
        sensitivity_value=0.85,
        elasticity=1.2,
        delta=0.75,
        position_id=position_id,
        gamma=0.02,
        theta=-0.001,
        vega=0.45,
        rho=0.12,
        parameters={"volatility": 0.35, "time_to_expiry": 30},
        status=SensitivityStatus.CALCULATED,
        metadata={"source": "black_scholes"}
    )

    print(f"   ID: {analysis.analysis_id}")
    print(f"   Symbole: {analysis.symbol}")
    print(f"   Sensibilité: {analysis.sensitivity_value:.2f}")
    print(f"   Élasticité: {analysis.elasticity:.2f}")
    print(f"   Delta: {analysis.delta:.2f}")
    print(f"   Gamma: {analysis.gamma:.4f}")

    # Création d'un facteur de sensibilité
    print(f"\n📈 Création d'un facteur de sensibilité...")
    
    factor = create_sensitivity_factor(
        analysis_id=analysis.analysis_id,
        user_id=user_id,
        name="Volatilité",
        factor_type="market",
        value=0.35,
        weight=0.60,
        impact=0.45,
        description="Facteur de volatilité de marché"
    )

    print(f"   ID: {factor.factor_id}")
    print(f"   Nom: {factor.name}")
    print(f"   Valeur: {factor.value:.2%}")
    print(f"   Impact: {factor.impact:.2%}")

    # Métriques de sensibilité
    print(f"\n📊 Métriques de sensibilité:")
    
    metrics = SensitivityMetrics(
        metric_id=uuid4(),
        analysis_id=analysis.analysis_id,
        user_id=user_id,
        total_sensitivity=2.45,
        average_sensitivity=0.82,
        max_sensitivity=1.20,
        min_sensitivity=0.35,
        sensitivity_ratio=0.75,
        factor_count=3
    )

    print(f"   Sensibilité totale: {metrics.total_sensitivity:.2f}")
    print(f"   Sensibilité moyenne: {metrics.average_sensitivity:.2f}")
    print(f"   Ratio de sensibilité: {metrics.sensitivity_ratio:.2f}")
    print(f"   Nombre de facteurs: {metrics.factor_count}")

    # Création d'un scénario de sensibilité
    print(f"\n🎯 Création d'un scénario de sensibilité...")
    
    scenario = SensitivityScenario(
        scenario_id=uuid4(),
        analysis_id=analysis.analysis_id,
        user_id=user_id,
        name="Volatilité +20%",
        description="Scénario de choc de volatilité",
        variables={"volatility": 0.42},
        outcomes={"price_change": -0.08, "delta_change": 0.12},
        probability=0.15
    )

    print(f"   ID: {scenario.scenario_id}")
    print(f"   Nom: {scenario.name}")
    print(f"   Variables: {scenario.variables}")
    print(f"   Probabilité: {scenario.probability:.1%}")

    print("\n" + "=" * 60)
    print("Sensitivity Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
