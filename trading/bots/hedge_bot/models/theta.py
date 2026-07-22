"""
NEXUS AI TRADING SYSTEM - HEDGE BOT THETA MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données Theta pour le Hedge Bot.
Définition des entités Theta, décroissance temporelle, et métriques associées.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
import math
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

class ThetaType(Enum):
    """Types de Theta."""
    THETA = "theta"
    THETA_DECAY = "theta_decay"
    THETA_IMPACT = "theta_impact"
    THETA_RATIO = "theta_ratio"
    THETA_DAILY = "theta_daily"
    THETA_WEEKLY = "theta_weekly"


class TimeDecayType(Enum):
    """Types de décroissance temporelle."""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    POWER = "power"
    PARABOLIC = "parabolic"
    LOGISTIC = "logistic"
    GOMBERTZ = "gombertz"


class ThetaRiskCategory(Enum):
    """Catégories de risque Theta."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class ThetaResultModel(Base):
    """Modèle de résultat Theta."""
    __tablename__ = "theta_results"

    result_id = Column(String(36), primary_key=True)
    option_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    underlying_symbol = Column(String(50), nullable=False)
    strike_price = Column(Numeric(20, 8), nullable=False)
    time_to_expiry = Column(Float, nullable=False)
    risk_free_rate = Column(Float, nullable=False)
    volatility = Column(Float, nullable=False)
    option_type = Column(String(10), nullable=False)
    theta = Column(Float, nullable=False)
    theta_decay = Column(Float, nullable=False)
    theta_impact = Column(Float, nullable=False)
    theta_ratio = Column(Float, nullable=False)
    theta_daily = Column(Float, nullable=False)
    theta_weekly = Column(Float, nullable=False)
    time_value = Column(Float, nullable=False)
    intrinsic_value = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_theta_results_user_id", "user_id"),
        Index("idx_theta_results_option_id", "option_id"),
        Index("idx_theta_results_underlying", "underlying_symbol"),
        Index("idx_theta_results_calculated_at", "calculated_at"),
    )


class ThetaExposureModel(Base):
    """Modèle d'exposition Theta."""
    __tablename__ = "theta_exposures"

    exposure_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    option_id = Column(String(36), nullable=False)
    portfolio_id = Column(String(36), nullable=True)
    theta_exposure = Column(Float, nullable=False)
    theta_exposure_usd = Column(Numeric(20, 8), nullable=False)
    theta_hedge_ratio = Column(Float, nullable=False)
    time_decay_rate = Column(Float, nullable=False)
    time_value_percent = Column(Float, nullable=False)
    theta_risk = Column(Float, nullable=False)
    theta_risk_category = Column(SQLEnum(ThetaRiskCategory), nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_theta_exposures_user_id", "user_id"),
        Index("idx_theta_exposures_option_id", "option_id"),
        Index("idx_theta_exposures_portfolio_id", "portfolio_id"),
        Index("idx_theta_exposures_calculated_at", "calculated_at"),
    )


class TimeDecayScheduleModel(Base):
    """Modèle de calendrier de décroissance temporelle."""
    __tablename__ = "time_decay_schedules"

    schedule_id = Column(String(36), primary_key=True)
    option_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    dates = Column(JSON, nullable=False)
    theta_values = Column(JSON, nullable=False)
    time_values = Column(JSON, nullable=False)
    intrinsic_values = Column(JSON, nullable=False)
    decay_type = Column(SQLEnum(TimeDecayType), nullable=False)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_time_decay_schedules_user_id", "user_id"),
        Index("idx_time_decay_schedules_option_id", "option_id"),
        Index("idx_time_decay_schedules_decay_type", "decay_type"),
    )


class ThetaMetricsModel(Base):
    """Modèle de métriques Theta."""
    __tablename__ = "theta_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    option_id = Column(String(36), nullable=False)
    portfolio_id = Column(String(36), nullable=True)
    total_theta_exposure = Column(Float, nullable=False)
    total_theta_exposure_usd = Column(Numeric(20, 8), nullable=False)
    average_theta = Column(Float, nullable=False)
    max_theta = Column(Float, nullable=False)
    min_theta = Column(Float, nullable=False)
    theta_decay_rate = Column(Float, nullable=False)
    theta_efficiency = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_theta_metrics_user_id", "user_id"),
        Index("idx_theta_metrics_option_id", "option_id"),
        Index("idx_theta_metrics_portfolio_id", "portfolio_id"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class ThetaResult:
    """Résultat Theta."""
    result_id: UUID
    option_id: UUID
    user_id: UUID
    underlying_symbol: str
    strike_price: Decimal
    time_to_expiry: float
    risk_free_rate: float
    volatility: float
    option_type: str
    theta: float
    theta_decay: float
    theta_impact: float
    theta_ratio: float
    theta_daily: float
    theta_weekly: float
    time_value: float
    intrinsic_value: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "result_id": str(self.result_id),
            "option_id": str(self.option_id),
            "user_id": str(self.user_id),
            "underlying_symbol": self.underlying_symbol,
            "strike_price": str(self.strike_price),
            "time_to_expiry": self.time_to_expiry,
            "risk_free_rate": self.risk_free_rate,
            "volatility": self.volatility,
            "option_type": self.option_type,
            "theta": self.theta,
            "theta_decay": self.theta_decay,
            "theta_impact": self.theta_impact,
            "theta_ratio": self.theta_ratio,
            "theta_daily": self.theta_daily,
            "theta_weekly": self.theta_weekly,
            "time_value": self.time_value,
            "intrinsic_value": self.intrinsic_value,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ThetaExposure:
    """Exposition Theta."""
    exposure_id: UUID
    user_id: UUID
    option_id: UUID
    portfolio_id: Optional[UUID]
    theta_exposure: float
    theta_exposure_usd: Decimal
    theta_hedge_ratio: float
    time_decay_rate: float
    time_value_percent: float
    theta_risk: float
    theta_risk_category: ThetaRiskCategory
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "exposure_id": str(self.exposure_id),
            "user_id": str(self.user_id),
            "option_id": str(self.option_id),
            "portfolio_id": str(self.portfolio_id) if self.portfolio_id else None,
            "theta_exposure": self.theta_exposure,
            "theta_exposure_usd": str(self.theta_exposure_usd),
            "theta_hedge_ratio": self.theta_hedge_ratio,
            "time_decay_rate": self.time_decay_rate,
            "time_value_percent": self.time_value_percent,
            "theta_risk": self.theta_risk,
            "theta_risk_category": self.theta_risk_category.value,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class TimeDecaySchedule:
    """Calendrier de décroissance temporelle."""
    schedule_id: UUID
    option_id: UUID
    user_id: UUID
    dates: List[datetime]
    theta_values: List[float]
    time_values: List[float]
    intrinsic_values: List[float]
    decay_type: TimeDecayType
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "schedule_id": str(self.schedule_id),
            "option_id": str(self.option_id),
            "user_id": str(self.user_id),
            "dates": [d.isoformat() for d in self.dates],
            "theta_values": self.theta_values,
            "time_values": self.time_values,
            "intrinsic_values": self.intrinsic_values,
            "decay_type": self.decay_type.value,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ThetaMetrics:
    """Métriques Theta."""
    metric_id: UUID
    user_id: UUID
    option_id: UUID
    portfolio_id: Optional[UUID]
    total_theta_exposure: float
    total_theta_exposure_usd: Decimal
    average_theta: float
    max_theta: float
    min_theta: float
    theta_decay_rate: float
    theta_efficiency: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "option_id": str(self.option_id),
            "portfolio_id": str(self.portfolio_id) if self.portfolio_id else None,
            "total_theta_exposure": self.total_theta_exposure,
            "total_theta_exposure_usd": str(self.total_theta_exposure_usd),
            "average_theta": self.average_theta,
            "max_theta": self.max_theta,
            "min_theta": self.min_theta,
            "theta_decay_rate": self.theta_decay_rate,
            "theta_efficiency": self.theta_efficiency,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_theta_result(
    option_id: UUID,
    user_id: UUID,
    underlying_symbol: str,
    strike_price: Decimal,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    option_type: str,
    theta: float,
    theta_decay: float,
    theta_impact: float,
    theta_ratio: float,
    theta_daily: float,
    theta_weekly: float,
    time_value: float,
    intrinsic_value: float,
    metadata: Optional[Dict] = None
) -> ThetaResult:
    """
    Crée un résultat Theta.

    Args:
        option_id: ID de l'option
        user_id: ID de l'utilisateur
        underlying_symbol: Symbole du sous-jacent
        strike_price: Prix d'exercice
        time_to_expiry: Temps jusqu'à l'expiration
        risk_free_rate: Taux sans risque
        volatility: Volatilité
        option_type: Type d'option
        theta: Theta
        theta_decay: Décroissance Theta
        theta_impact: Impact Theta
        theta_ratio: Ratio Theta
        theta_daily: Theta quotidien
        theta_weekly: Theta hebdomadaire
        time_value: Valeur temps
        intrinsic_value: Valeur intrinsèque
        metadata: Métadonnées

    Returns:
        Résultat Theta
    """
    return ThetaResult(
        result_id=uuid4(),
        option_id=option_id,
        user_id=user_id,
        underlying_symbol=underlying_symbol,
        strike_price=strike_price,
        time_to_expiry=time_to_expiry,
        risk_free_rate=risk_free_rate,
        volatility=volatility,
        option_type=option_type,
        theta=theta,
        theta_decay=theta_decay,
        theta_impact=theta_impact,
        theta_ratio=theta_ratio,
        theta_daily=theta_daily,
        theta_weekly=theta_weekly,
        time_value=time_value,
        intrinsic_value=intrinsic_value,
        metadata=metadata or {}
    )


def create_time_decay_schedule(
    option_id: UUID,
    user_id: UUID,
    dates: List[datetime],
    theta_values: List[float],
    time_values: List[float],
    intrinsic_values: List[float],
    decay_type: TimeDecayType = TimeDecayType.EXPONENTIAL,
    metadata: Optional[Dict] = None
) -> TimeDecaySchedule:
    """
    Crée un calendrier de décroissance temporelle.

    Args:
        option_id: ID de l'option
        user_id: ID de l'utilisateur
        dates: Dates
        theta_values: Valeurs Theta
        time_values: Valeurs temps
        intrinsic_values: Valeurs intrinsèques
        decay_type: Type de décroissance
        metadata: Métadonnées

    Returns:
        Calendrier de décroissance temporelle
    """
    return TimeDecaySchedule(
        schedule_id=uuid4(),
        option_id=option_id,
        user_id=user_id,
        dates=dates,
        theta_values=theta_values,
        time_values=time_values,
        intrinsic_values=intrinsic_values,
        decay_type=decay_type,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ThetaType",
    "TimeDecayType",
    "ThetaRiskCategory",
    "ThetaResultModel",
    "ThetaExposureModel",
    "TimeDecayScheduleModel",
    "ThetaMetricsModel",
    "ThetaResult",
    "ThetaExposure",
    "TimeDecaySchedule",
    "ThetaMetrics",
    "create_theta_result",
    "create_time_decay_schedule"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles Theta."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT THETA MODELS")
    print("=" * 60)

    # Création d'un résultat Theta
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    option_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'un résultat Theta...")
    
    result = create_theta_result(
        option_id=option_id,
        user_id=user_id,
        underlying_symbol="BTC/USDT",
        strike_price=Decimal("50000"),
        time_to_expiry=0.25,
        risk_free_rate=0.02,
        volatility=0.35,
        option_type="call",
        theta=-0.015,
        theta_decay=0.12,
        theta_impact=-0.0015,
        theta_ratio=0.08,
        theta_daily=-0.00006,
        theta_weekly=-0.00042,
        time_value=0.08,
        intrinsic_value=0.02,
        metadata={"source": "black_scholes"}
    )

    print(f"   ID: {result.result_id}")
    print(f"   Theta: {result.theta:.4f}")
    print(f"   Theta Daily: {result.theta_daily:.6f}")
    print(f"   Theta Weekly: {result.theta_weekly:.6f}")
    print(f"   Time Value: {result.time_value:.4f}")
    print(f"   Intrinsic Value: {result.intrinsic_value:.4f}")

    # Création d'une exposition Theta
    print(f"\n📈 Création d'une exposition Theta...")
    
    exposure = ThetaExposure(
        exposure_id=uuid4(),
        user_id=user_id,
        option_id=option_id,
        portfolio_id=None,
        theta_exposure=0.015,
        theta_exposure_usd=Decimal("1500"),
        theta_hedge_ratio=0.75,
        time_decay_rate=0.12,
        time_value_percent=80.0,
        theta_risk=0.035,
        theta_risk_category=ThetaRiskCategory.MEDIUM
    )

    print(f"   ID: {exposure.exposure_id}")
    print(f"   Exposition: {exposure.theta_exposure:.4f}")
    print(f"   Exposition USD: ${exposure.theta_exposure_usd}")
    print(f"   Décroissance: {exposure.time_decay_rate:.2%}")
    print(f"   Risque: {exposure.theta_risk_category.value}")

    # Création d'un calendrier de décroissance
    print(f"\n📅 Création d'un calendrier de décroissance...")
    
    dates = [datetime.now() + timedelta(days=i) for i in range(10)]
    theta_values = [-0.015, -0.016, -0.017, -0.018, -0.019, -0.020, -0.021, -0.022, -0.023, -0.024]
    time_values = [0.08, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 0.035]
    intrinsic_values = [0.02] * 10

    schedule = create_time_decay_schedule(
        option_id=option_id,
        user_id=user_id,
        dates=dates,
        theta_values=theta_values,
        time_values=time_values,
        intrinsic_values=intrinsic_values,
        decay_type=TimeDecayType.EXPONENTIAL
    )

    print(f"   ID: {schedule.schedule_id}")
    print(f"   Type: {schedule.decay_type.value}")
    print(f"   Theta initial: {schedule.theta_values[0]:.4f}")
    print(f"   Theta final: {schedule.theta_values[-1]:.4f}")

    # Métriques Theta
    print(f"\n📊 Métriques Theta:")
    
    metrics = ThetaMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        option_id=option_id,
        portfolio_id=None,
        total_theta_exposure=0.015,
        total_theta_exposure_usd=Decimal("1500"),
        average_theta=0.015,
        max_theta=0.018,
        min_theta=0.012,
        theta_decay_rate=0.12,
        theta_efficiency=0.75
    )

    print(f"   Exposition totale: {metrics.total_theta_exposure:.4f}")
    print(f"   Taux de décroissance: {metrics.theta_decay_rate:.2%}")
    print(f"   Efficacité: {metrics.theta_efficiency:.2%}")

    print("\n" + "=" * 60)
    print("Theta Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
