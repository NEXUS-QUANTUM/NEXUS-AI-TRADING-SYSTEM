"""
NEXUS AI TRADING SYSTEM - HEDGE BOT PROFIT TARGET MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de profit target pour le Hedge Bot.
Définition des entités de profit target, niveaux, et métriques associées.

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

class ProfitTargetType(Enum):
    """Types de profit target."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    VOLATILITY = "volatility"
    ATR = "atr"
    FIBONACCI = "fibonacci"
    RESISTANCE = "resistance"
    DYNAMIC = "dynamic"
    SCALING = "scaling"
    RISK_REWARD = "risk_reward"
    PARTIAL = "partial"


class ProfitTargetStatus(Enum):
    """Statuts de profit target."""
    PENDING = "pending"
    ACTIVE = "active"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    EXCEEDED = "exceeded"


class ProfitTargetEfficiency(Enum):
    """Niveaux d'efficacité de profit target."""
    POOR = "poor"
    AVERAGE = "average"
    GOOD = "good"
    EXCELLENT = "excellent"
    PERFECT = "perfect"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class ProfitTargetModel(Base):
    """Modèle de profit target."""
    __tablename__ = "profit_targets"

    target_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    target_type = Column(SQLEnum(ProfitTargetType), nullable=False)
    status = Column(SQLEnum(ProfitTargetStatus), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    target_price = Column(Numeric(20, 8), nullable=False)
    target_percent = Column(Float, nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    quantity_filled = Column(Numeric(20, 8), nullable=False)
    realized_profit = Column(Numeric(20, 8), nullable=True)
    realized_profit_percent = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_profit_targets_user_id", "user_id"),
        Index("idx_profit_targets_position_id", "position_id"),
        Index("idx_profit_targets_symbol", "symbol"),
        Index("idx_profit_targets_status", "status"),
        Index("idx_profit_targets_type", "target_type"),
        Index("idx_profit_targets_created_at", "created_at"),
    )


class ProfitTargetScheduleModel(Base):
    """Modèle de calendrier de profit target."""
    __tablename__ = "profit_target_schedules"

    schedule_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    levels = Column(JSON, nullable=False)
    total_quantity = Column(Numeric(20, 8), nullable=False)
    remaining_quantity = Column(Numeric(20, 8), nullable=False)
    total_target_percent = Column(Float, nullable=False)
    status = Column(SQLEnum(ProfitTargetStatus), nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_profit_target_schedules_user_id", "user_id"),
        Index("idx_profit_target_schedules_position_id", "position_id"),
        Index("idx_profit_target_schedules_symbol", "symbol"),
        Index("idx_profit_target_schedules_status", "status"),
    )


class ProfitTargetMetricsModel(Base):
    """Modèle de métriques de profit target."""
    __tablename__ = "profit_target_metrics"

    metric_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    total_profit = Column(Numeric(20, 8), nullable=False)
    total_profit_usd = Column(Numeric(20, 8), nullable=False)
    average_profit_percent = Column(Float, nullable=False)
    max_profit_percent = Column(Float, nullable=False)
    min_profit_percent = Column(Float, nullable=False)
    profit_factor = Column(Float, nullable=False)
    win_rate = Column(Float, nullable=False)
    efficiency_score = Column(Float, nullable=True)
    efficiency_level = Column(SQLEnum(ProfitTargetEfficiency), nullable=True)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_profit_target_metrics_user_id", "user_id"),
        Index("idx_profit_target_metrics_position_id", "position_id"),
        Index("idx_profit_target_metrics_calculated_at", "calculated_at"),
    )


class ProfitTargetHistoryModel(Base):
    """Modèle d'historique de profit target."""
    __tablename__ = "profit_target_history"

    history_id = Column(String(36), primary_key=True)
    target_id = Column(String(36), ForeignKey("profit_targets.target_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    profit = Column(Numeric(20, 8), nullable=False)
    profit_percent = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

    # Relations
    target = relationship("ProfitTargetModel")

    __table_args__ = (
        Index("idx_profit_target_history_target_id", "target_id"),
        Index("idx_profit_target_history_user_id", "user_id"),
        Index("idx_profit_target_history_timestamp", "timestamp"),
    )


class ProfitTargetOptimizationModel(Base):
    """Modèle d'optimisation de profit target."""
    __tablename__ = "profit_target_optimizations"

    optimization_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    target_type = Column(SQLEnum(ProfitTargetType), nullable=False)
    parameters = Column(JSON, nullable=False)
    performance_score = Column(Float, nullable=False)
    expected_profit = Column(Numeric(20, 8), nullable=False)
    win_rate = Column(Float, nullable=False)
    profit_factor = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_profit_target_optimizations_user_id", "user_id"),
        Index("idx_profit_target_optimizations_position_id", "position_id"),
        Index("idx_profit_target_optimizations_symbol", "symbol"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class ProfitTarget:
    """Profit target."""
    target_id: UUID
    position_id: UUID
    user_id: UUID
    symbol: str
    target_type: ProfitTargetType
    status: ProfitTargetStatus
    entry_price: Decimal
    target_price: Decimal
    target_percent: float
    quantity: Decimal
    quantity_filled: Decimal
    realized_profit: Optional[Decimal]
    realized_profit_percent: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    activated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "target_id": str(self.target_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "target_type": self.target_type.value,
            "status": self.status.value,
            "entry_price": str(self.entry_price),
            "target_price": str(self.target_price),
            "target_percent": self.target_percent,
            "quantity": str(self.quantity),
            "quantity_filled": str(self.quantity_filled),
            "realized_profit": str(self.realized_profit) if self.realized_profit else None,
            "realized_profit_percent": self.realized_profit_percent,
            "metadata": self.metadata,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class ProfitTargetSchedule:
    """Calendrier de profit target."""
    schedule_id: UUID
    position_id: UUID
    user_id: UUID
    symbol: str
    levels: List[Dict[str, Any]]
    total_quantity: Decimal
    remaining_quantity: Decimal
    total_target_percent: float
    status: ProfitTargetStatus
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "schedule_id": str(self.schedule_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "levels": self.levels,
            "total_quantity": str(self.total_quantity),
            "remaining_quantity": str(self.remaining_quantity),
            "total_target_percent": self.total_target_percent,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class ProfitTargetMetrics:
    """Métriques de profit target."""
    metric_id: UUID
    position_id: UUID
    user_id: UUID
    total_profit: Decimal
    total_profit_usd: Decimal
    average_profit_percent: float
    max_profit_percent: float
    min_profit_percent: float
    profit_factor: float
    win_rate: float
    efficiency_score: Optional[float] = None
    efficiency_level: Optional[ProfitTargetEfficiency] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "total_profit": str(self.total_profit),
            "total_profit_usd": str(self.total_profit_usd),
            "average_profit_percent": self.average_profit_percent,
            "max_profit_percent": self.max_profit_percent,
            "min_profit_percent": self.min_profit_percent,
            "profit_factor": self.profit_factor,
            "win_rate": self.win_rate,
            "efficiency_score": self.efficiency_score,
            "efficiency_level": self.efficiency_level.value if self.efficiency_level else None,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ProfitTargetHistory:
    """Historique de profit target."""
    history_id: UUID
    target_id: UUID
    user_id: UUID
    position_id: UUID
    timestamp: datetime
    price: Decimal
    profit: Decimal
    profit_percent: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "history_id": str(self.history_id),
            "target_id": str(self.target_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id),
            "timestamp": self.timestamp.isoformat(),
            "price": str(self.price),
            "profit": str(self.profit),
            "profit_percent": self.profit_percent,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ProfitTargetOptimization:
    """Optimisation de profit target."""
    optimization_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    symbol: str
    target_type: ProfitTargetType
    parameters: Dict[str, Any]
    performance_score: float
    expected_profit: Decimal
    win_rate: float
    profit_factor: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "optimization_id": str(self.optimization_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id) if self.position_id else None,
            "symbol": self.symbol,
            "target_type": self.target_type.value,
            "parameters": self.parameters,
            "performance_score": self.performance_score,
            "expected_profit": str(self.expected_profit),
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_profit_target(
    position_id: UUID,
    user_id: UUID,
    symbol: str,
    target_type: ProfitTargetType,
    entry_price: Decimal,
    target_price: Decimal,
    target_percent: float,
    quantity: Decimal,
    status: ProfitTargetStatus = ProfitTargetStatus.PENDING,
    metadata: Optional[Dict] = None
) -> ProfitTarget:
    """
    Crée un profit target.

    Args:
        position_id: ID de la position
        user_id: ID de l'utilisateur
        symbol: Symbole
        target_type: Type de profit target
        entry_price: Prix d'entrée
        target_price: Prix cible
        target_percent: Pourcentage cible
        quantity: Quantité
        status: Statut
        metadata: Métadonnées

    Returns:
        Profit target créé
    """
    return ProfitTarget(
        target_id=uuid4(),
        position_id=position_id,
        user_id=user_id,
        symbol=symbol,
        target_type=target_type,
        status=status,
        entry_price=entry_price,
        target_price=target_price,
        target_percent=target_percent,
        quantity=quantity,
        quantity_filled=Decimal("0"),
        realized_profit=None,
        realized_profit_percent=None,
        metadata=metadata or {}
    )


def create_profit_target_metrics(
    position_id: UUID,
    user_id: UUID,
    total_profit: Decimal,
    total_profit_usd: Decimal,
    average_profit_percent: float,
    max_profit_percent: float,
    min_profit_percent: float,
    profit_factor: float,
    win_rate: float,
    efficiency_score: Optional[float] = None,
    efficiency_level: Optional[ProfitTargetEfficiency] = None,
    metadata: Optional[Dict] = None
) -> ProfitTargetMetrics:
    """
    Crée des métriques de profit target.

    Args:
        position_id: ID de la position
        user_id: ID de l'utilisateur
        total_profit: Profit total
        total_profit_usd: Profit total en USD
        average_profit_percent: Profit moyen
        max_profit_percent: Profit maximum
        min_profit_percent: Profit minimum
        profit_factor: Facteur de profit
        win_rate: Taux de victoire
        efficiency_score: Score d'efficacité
        efficiency_level: Niveau d'efficacité
        metadata: Métadonnées

    Returns:
        Métriques de profit target
    """
    return ProfitTargetMetrics(
        metric_id=uuid4(),
        position_id=position_id,
        user_id=user_id,
        total_profit=total_profit,
        total_profit_usd=total_profit_usd,
        average_profit_percent=average_profit_percent,
        max_profit_percent=max_profit_percent,
        min_profit_percent=min_profit_percent,
        profit_factor=profit_factor,
        win_rate=win_rate,
        efficiency_score=efficiency_score,
        efficiency_level=efficiency_level,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ProfitTargetType",
    "ProfitTargetStatus",
    "ProfitTargetEfficiency",
    "ProfitTargetModel",
    "ProfitTargetScheduleModel",
    "ProfitTargetMetricsModel",
    "ProfitTargetHistoryModel",
    "ProfitTargetOptimizationModel",
    "ProfitTarget",
    "ProfitTargetSchedule",
    "ProfitTargetMetrics",
    "ProfitTargetHistory",
    "ProfitTargetOptimization",
    "create_profit_target",
    "create_profit_target_metrics"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de profit target."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT PROFIT TARGET MODELS")
    print("=" * 60)

    # Création d'un profit target
    position_id = UUID("12345678-1234-5678-1234-567812345678")
    user_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'un profit target...")
    
    target = create_profit_target(
        position_id=position_id,
        user_id=user_id,
        symbol="BTC/USDT",
        target_type=ProfitTargetType.PERCENTAGE,
        entry_price=Decimal("50000"),
        target_price=Decimal("52500"),
        target_percent=0.05,
        quantity=Decimal("0.1"),
        metadata={"strategy": "swing_trading"}
    )

    print(f"   ID: {target.target_id}")
    print(f"   Entrée: ${target.entry_price}")
    print(f"   Cible: ${target.target_price}")
    print(f"   %: {target.target_percent*100:.1f}%")
    print(f"   Quantité: {target.quantity}")

    # Création d'un calendrier de profit target
    print(f"\n📅 Création d'un calendrier de profit target...")
    
    schedule = ProfitTargetSchedule(
        schedule_id=uuid4(),
        position_id=position_id,
        user_id=user_id,
        symbol="BTC/USDT",
        levels=[
            {"target_percent": 0.02, "quantity": Decimal("0.02")},
            {"target_percent": 0.05, "quantity": Decimal("0.03")},
            {"target_percent": 0.08, "quantity": Decimal("0.05")}
        ],
        total_quantity=Decimal("0.1"),
        remaining_quantity=Decimal("0.1"),
        total_target_percent=0.15,
        status=ProfitTargetStatus.ACTIVE
    )

    print(f"   ID: {schedule.schedule_id}")
    print(f"   Niveaux: {len(schedule.levels)}")
    print(f"   Quantité totale: {schedule.total_quantity}")

    # Métriques
    print(f"\n📈 Métriques de profit target:")
    
    metrics = create_profit_target_metrics(
        position_id=position_id,
        user_id=user_id,
        total_profit=Decimal("250"),
        total_profit_usd=Decimal("250"),
        average_profit_percent=3.5,
        max_profit_percent=5.0,
        min_profit_percent=2.0,
        profit_factor=1.8,
        win_rate=0.75,
        efficiency_score=0.85,
        efficiency_level=ProfitTargetEfficiency.GOOD
    )

    print(f"   Profit total: ${metrics.total_profit}")
    print(f"   Profit moyen: {metrics.average_profit_percent:.1f}%")
    print(f"   Win rate: {metrics.win_rate*100:.1f}%")
    print(f"   Efficacité: {metrics.efficiency_level.value}")

    # Optimisation
    print(f"\n🎯 Optimisation de profit target...")
    
    optimization = ProfitTargetOptimization(
        optimization_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        symbol="BTC/USDT",
        target_type=ProfitTargetType.RISK_REWARD,
        parameters={"risk_reward_ratio": 2.5, "scaling": True},
        performance_score=0.92,
        expected_profit=Decimal("350"),
        win_rate=0.68,
        profit_factor=1.95
    )

    print(f"   Score: {optimization.performance_score:.2%}")
    print(f"   Profit attendu: ${optimization.expected_profit}")
    print(f"   Profit factor: {optimization.profit_factor:.2f}")

    print("\n" + "=" * 60)
    print("Profit Target Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
