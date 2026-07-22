"""
NEXUS AI TRADING SYSTEM - HEDGE BOT POSITION SIZE MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de taille de position pour le Hedge Bot.
Définition des entités de position sizing, métriques, et optimisations.

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

class PositionSizingMethod(Enum):
    """Méthodes de dimensionnement de position."""
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    KELLY = "kelly"
    VOLATILITY = "volatility"
    RISK_REWARD = "risk_reward"
    OPTIMAL = "optimal"
    ADAPTIVE = "adaptive"
    MARTINGALE = "martingale"
    ANTI_MARTINGALE = "anti_martingale"


class PositionSizeStatus(Enum):
    """Statuts de position sizing."""
    PENDING = "pending"
    CALCULATED = "calculated"
    OPTIMIZED = "optimized"
    ACTIVE = "active"
    CLOSED = "closed"
    ERROR = "error"


class PositionSizeLevel(Enum):
    """Niveaux de position sizing."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    MAXIMUM = "maximum"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class PositionSizeModel(Base):
    """Modèle de taille de position."""
    __tablename__ = "position_sizes"

    position_size_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    method = Column(SQLEnum(PositionSizingMethod), nullable=False)
    status = Column(SQLEnum(PositionSizeStatus), nullable=False)
    level = Column(SQLEnum(PositionSizeLevel), nullable=True)
    base_size = Column(Numeric(20, 8), nullable=False)
    adjusted_size = Column(Numeric(20, 8), nullable=False)
    max_size = Column(Numeric(20, 8), nullable=False)
    min_size = Column(Numeric(20, 8), nullable=False)
    risk_percentage = Column(Float, nullable=False)
    risk_amount = Column(Numeric(20, 8), nullable=False)
    kelly_fraction = Column(Float, nullable=True)
    volatility_factor = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_position_sizes_user_id", "user_id"),
        Index("idx_position_sizes_position_id", "position_id"),
        Index("idx_position_sizes_symbol", "symbol"),
        Index("idx_position_sizes_method", "method"),
        Index("idx_position_sizes_status", "status"),
        Index("idx_position_sizes_calculated_at", "calculated_at"),
    )


class PositionSizeMetricsModel(Base):
    """Modèle de métriques de position sizing."""
    __tablename__ = "position_size_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=False)
    total_position_size = Column(Numeric(20, 8), nullable=False)
    average_position_size = Column(Numeric(20, 8), nullable=False)
    max_position_size = Column(Numeric(20, 8), nullable=False)
    min_position_size = Column(Numeric(20, 8), nullable=False)
    size_efficiency = Column(Float, nullable=False)
    risk_adjusted_size = Column(Numeric(20, 8), nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_position_size_metrics_user_id", "user_id"),
        Index("idx_position_size_metrics_position_id", "position_id"),
        Index("idx_position_size_metrics_calculated_at", "calculated_at"),
    )


class PositionSizeOptimizationModel(Base):
    """Modèle d'optimisation de position sizing."""
    __tablename__ = "position_size_optimizations"

    optimization_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    method = Column(SQLEnum(PositionSizingMethod), nullable=False)
    parameters = Column(JSON, nullable=False)
    optimal_size = Column(Numeric(20, 8), nullable=False)
    expected_return = Column(Numeric(20, 8), nullable=False)
    max_drawdown = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_position_size_optimizations_user_id", "user_id"),
        Index("idx_position_size_optimizations_symbol", "symbol"),
        Index("idx_position_size_optimizations_method", "method"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class PositionSize:
    """Taille de position."""
    position_size_id: UUID
    position_id: UUID
    user_id: UUID
    symbol: str
    method: PositionSizingMethod
    status: PositionSizeStatus
    level: Optional[PositionSizeLevel]
    base_size: Decimal
    adjusted_size: Decimal
    max_size: Decimal
    min_size: Decimal
    risk_percentage: float
    risk_amount: Decimal
    kelly_fraction: Optional[float]
    volatility_factor: Optional[float]
    confidence_score: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "position_size_id": str(self.position_size_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "method": self.method.value,
            "status": self.status.value,
            "level": self.level.value if self.level else None,
            "base_size": str(self.base_size),
            "adjusted_size": str(self.adjusted_size),
            "max_size": str(self.max_size),
            "min_size": str(self.min_size),
            "risk_percentage": self.risk_percentage,
            "risk_amount": str(self.risk_amount),
            "kelly_fraction": self.kelly_fraction,
            "volatility_factor": self.volatility_factor,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class PositionSizeMetrics:
    """Métriques de position sizing."""
    metric_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    total_position_size: Decimal
    average_position_size: Decimal
    max_position_size: Decimal
    min_position_size: Decimal
    size_efficiency: float
    risk_adjusted_size: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id) if self.position_id else None,
            "total_position_size": str(self.total_position_size),
            "average_position_size": str(self.average_position_size),
            "max_position_size": str(self.max_position_size),
            "min_position_size": str(self.min_position_size),
            "size_efficiency": self.size_efficiency,
            "risk_adjusted_size": str(self.risk_adjusted_size),
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class PositionSizeOptimization:
    """Optimisation de position sizing."""
    optimization_id: UUID
    user_id: UUID
    symbol: str
    method: PositionSizingMethod
    parameters: Dict[str, Any]
    optimal_size: Decimal
    expected_return: Decimal
    max_drawdown: float
    sharpe_ratio: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "optimization_id": str(self.optimization_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "method": self.method.value,
            "parameters": self.parameters,
            "optimal_size": str(self.optimal_size),
            "expected_return": str(self.expected_return),
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_position_size(
    position_id: UUID,
    user_id: UUID,
    symbol: str,
    method: PositionSizingMethod,
    base_size: Decimal,
    adjusted_size: Decimal,
    max_size: Decimal,
    min_size: Decimal,
    risk_percentage: float,
    risk_amount: Decimal,
    status: PositionSizeStatus = PositionSizeStatus.CALCULATED,
    level: Optional[PositionSizeLevel] = None,
    kelly_fraction: Optional[float] = None,
    volatility_factor: Optional[float] = None,
    confidence_score: Optional[float] = None,
    metadata: Optional[Dict] = None
) -> PositionSize:
    """
    Crée une taille de position.

    Args:
        position_id: ID de la position
        user_id: ID de l'utilisateur
        symbol: Symbole
        method: Méthode de dimensionnement
        base_size: Taille de base
        adjusted_size: Taille ajustée
        max_size: Taille maximale
        min_size: Taille minimale
        risk_percentage: Pourcentage de risque
        risk_amount: Montant de risque
        status: Statut
        level: Niveau
        kelly_fraction: Fraction Kelly
        volatility_factor: Facteur de volatilité
        confidence_score: Score de confiance
        metadata: Métadonnées

    Returns:
        Taille de position
    """
    return PositionSize(
        position_size_id=uuid4(),
        position_id=position_id,
        user_id=user_id,
        symbol=symbol,
        method=method,
        status=status,
        level=level,
        base_size=base_size,
        adjusted_size=adjusted_size,
        max_size=max_size,
        min_size=min_size,
        risk_percentage=risk_percentage,
        risk_amount=risk_amount,
        kelly_fraction=kelly_fraction,
        volatility_factor=volatility_factor,
        confidence_score=confidence_score,
        metadata=metadata or {}
    )


def create_position_size_metrics(
    user_id: UUID,
    total_position_size: Decimal,
    average_position_size: Decimal,
    max_position_size: Decimal,
    min_position_size: Decimal,
    size_efficiency: float,
    risk_adjusted_size: Decimal,
    position_id: Optional[UUID] = None,
    metadata: Optional[Dict] = None
) -> PositionSizeMetrics:
    """
    Crée des métriques de position sizing.

    Args:
        user_id: ID de l'utilisateur
        total_position_size: Taille totale des positions
        average_position_size: Taille moyenne
        max_position_size: Taille maximale
        min_position_size: Taille minimale
        size_efficiency: Efficacité de taille
        risk_adjusted_size: Taille ajustée au risque
        position_id: ID de la position
        metadata: Métadonnées

    Returns:
        Métriques de position sizing
    """
    return PositionSizeMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        total_position_size=total_position_size,
        average_position_size=average_position_size,
        max_position_size=max_position_size,
        min_position_size=min_position_size,
        size_efficiency=size_efficiency,
        risk_adjusted_size=risk_adjusted_size,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PositionSizingMethod",
    "PositionSizeStatus",
    "PositionSizeLevel",
    "PositionSizeModel",
    "PositionSizeMetricsModel",
    "PositionSizeOptimizationModel",
    "PositionSize",
    "PositionSizeMetrics",
    "PositionSizeOptimization",
    "create_position_size",
    "create_position_size_metrics"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de position sizing."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT POSITION SIZE MODELS")
    print("=" * 60)

    # Création d'une taille de position
    position_id = UUID("12345678-1234-5678-1234-567812345678")
    user_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'une taille de position...")
    
    position_size = create_position_size(
        position_id=position_id,
        user_id=user_id,
        symbol="BTC/USDT",
        method=PositionSizingMethod.KELLY,
        base_size=Decimal("0.1"),
        adjusted_size=Decimal("0.08"),
        max_size=Decimal("0.15"),
        min_size=Decimal("0.02"),
        risk_percentage=0.02,
        risk_amount=Decimal("200"),
        level=PositionSizeLevel.MEDIUM,
        kelly_fraction=0.25,
        volatility_factor=0.8,
        confidence_score=0.75,
        metadata={"strategy": "swing_trading"}
    )

    print(f"   ID: {position_size.position_size_id}")
    print(f"   Méthode: {position_size.method.value}")
    print(f"   Taille de base: {position_size.base_size}")
    print(f"   Taille ajustée: {position_size.adjusted_size}")
    print(f"   Kelly: {position_size.kelly_fraction:.2%}")
    print(f"   Confiance: {position_size.confidence_score:.1%}")

    # Métriques
    print(f"\n📈 Métriques de position sizing:")
    
    metrics = create_position_size_metrics(
        user_id=user_id,
        total_position_size=Decimal("0.5"),
        average_position_size=Decimal("0.08"),
        max_position_size=Decimal("0.15"),
        min_position_size=Decimal("0.02"),
        size_efficiency=0.85,
        risk_adjusted_size=Decimal("0.06")
    )

    print(f"   Taille totale: {metrics.total_position_size}")
    print(f"   Taille moyenne: {metrics.average_position_size}")
    print(f"   Efficacité: {metrics.size_efficiency:.1%}")

    # Optimisation
    print(f"\n🎯 Optimisation de position sizing:")
    
    optimization = PositionSizeOptimization(
        optimization_id=uuid4(),
        user_id=user_id,
        symbol="BTC/USDT",
        method=PositionSizingMethod.OPTIMAL,
        parameters={"risk_tolerance": 0.15, "target_return": 0.20},
        optimal_size=Decimal("0.12"),
        expected_return=Decimal("1200"),
        max_drawdown=0.08,
        sharpe_ratio=1.85
    )

    print(f"   Taille optimale: {optimization.optimal_size}")
    print(f"   Retour attendu: ${optimization.expected_return}")
    print(f"   Drawdown max: {optimization.max_drawdown:.1%}")
    print(f"   Sharpe Ratio: {optimization.sharpe_ratio:.2f}")

    print("\n" + "=" * 60)
    print("Position Size Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
