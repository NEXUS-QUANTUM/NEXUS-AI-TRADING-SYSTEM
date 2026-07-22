"""
NEXUS AI TRADING SYSTEM - HEDGE BOT STOP LOSS MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de stop loss pour le Hedge Bot.
Définition des entités de stop loss, niveaux, et métriques associées.

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

class StopLossType(Enum):
    """Types de stop loss."""
    FIXED = "fixed"
    TRAILING = "trailing"
    VOLATILITY = "volatility"
    ATR = "atr"
    DYNAMIC = "dynamic"
    SMART = "smart"
    ADAPTIVE = "adaptive"
    HYBRID = "hybrid"


class StopLossStatus(Enum):
    """Statuts de stop loss."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAUSED = "paused"


class StopLossActivation(Enum):
    """Modes d'activation de stop loss."""
    IMMEDIATE = "immediate"
    AT_PRICE = "at_price"
    AFTER_PROFIT = "after_profit"
    ON_BREAKOUT = "on_breakout"
    ON_VOLATILITY = "on_volatility"


class StopLossEfficiency(Enum):
    """Niveaux d'efficacité de stop loss."""
    POOR = "poor"
    AVERAGE = "average"
    GOOD = "good"
    EXCELLENT = "excellent"
    PERFECT = "perfect"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class StopLossModel(Base):
    """Modèle de stop loss."""
    __tablename__ = "stop_losses"

    stop_loss_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    stop_loss_type = Column(SQLEnum(StopLossType), nullable=False)
    status = Column(SQLEnum(StopLossStatus), nullable=False)
    activation_mode = Column(SQLEnum(StopLossActivation), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    stop_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=False)
    highest_price = Column(Numeric(20, 8), nullable=False)
    lowest_price = Column(Numeric(20, 8), nullable=False)
    stop_percent = Column(Float, nullable=True)
    stop_amount = Column(Numeric(20, 8), nullable=True)
    atr_period = Column(Integer, nullable=True)
    atr_multiplier = Column(Float, nullable=True)
    volatility_window = Column(Integer, nullable=True)
    metadata = Column(JSON, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_stop_losses_user_id", "user_id"),
        Index("idx_stop_losses_position_id", "position_id"),
        Index("idx_stop_losses_symbol", "symbol"),
        Index("idx_stop_losses_status", "status"),
        Index("idx_stop_losses_type", "stop_loss_type"),
        Index("idx_stop_losses_created_at", "created_at"),
    )


class StopLossMetricsModel(Base):
    """Modèle de métriques de stop loss."""
    __tablename__ = "stop_loss_metrics"

    metric_id = Column(String(36), primary_key=True)
    stop_loss_id = Column(String(36), ForeignKey("stop_losses.stop_loss_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=False)
    total_distance = Column(Numeric(20, 8), nullable=False)
    current_distance = Column(Numeric(20, 8), nullable=False)
    max_distance = Column(Numeric(20, 8), nullable=False)
    avg_distance = Column(Numeric(20, 8), nullable=False)
    stop_efficiency = Column(Float, nullable=False)
    loss_prevented = Column(Numeric(20, 8), nullable=False)
    volatility_adjusted = Column(Float, nullable=True)
    effectiveness_score = Column(Float, nullable=True)
    efficiency_level = Column(SQLEnum(StopLossEfficiency), nullable=True)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    stop_loss = relationship("StopLossModel")

    __table_args__ = (
        Index("idx_stop_loss_metrics_user_id", "user_id"),
        Index("idx_stop_loss_metrics_stop_loss_id", "stop_loss_id"),
        Index("idx_stop_loss_metrics_position_id", "position_id"),
        Index("idx_stop_loss_metrics_calculated_at", "calculated_at"),
    )


class StopLossHistoryModel(Base):
    """Modèle d'historique de stop loss."""
    __tablename__ = "stop_loss_history"

    history_id = Column(String(36), primary_key=True)
    stop_loss_id = Column(String(36), ForeignKey("stop_losses.stop_loss_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    stop_price = Column(Numeric(20, 8), nullable=False)
    highest_price = Column(Numeric(20, 8), nullable=False)
    lowest_price = Column(Numeric(20, 8), nullable=False)
    distance = Column(Numeric(20, 8), nullable=False)
    distance_percent = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

    # Relations
    stop_loss = relationship("StopLossModel")

    __table_args__ = (
        Index("idx_stop_loss_history_stop_loss_id", "stop_loss_id"),
        Index("idx_stop_loss_history_user_id", "user_id"),
        Index("idx_stop_loss_history_timestamp", "timestamp"),
    )


class StopLossOptimizationModel(Base):
    """Modèle d'optimisation de stop loss."""
    __tablename__ = "stop_loss_optimizations"

    optimization_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    stop_loss_type = Column(SQLEnum(StopLossType), nullable=False)
    parameters = Column(JSON, nullable=False)
    performance_score = Column(Float, nullable=False)
    loss_prevented = Column(Numeric(20, 8), nullable=False)
    trigger_frequency = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_stop_loss_optimizations_user_id", "user_id"),
        Index("idx_stop_loss_optimizations_position_id", "position_id"),
        Index("idx_stop_loss_optimizations_symbol", "symbol"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class StopLoss:
    """Stop loss."""
    stop_loss_id: UUID
    position_id: UUID
    user_id: UUID
    symbol: str
    stop_loss_type: StopLossType
    status: StopLossStatus
    activation_mode: StopLossActivation
    entry_price: Decimal
    stop_price: Decimal
    current_price: Decimal
    highest_price: Decimal
    lowest_price: Decimal
    stop_percent: Optional[float] = None
    stop_amount: Optional[Decimal] = None
    atr_period: Optional[int] = None
    atr_multiplier: Optional[float] = None
    volatility_window: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    activated_at: Optional[datetime] = None
    triggered_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "stop_loss_id": str(self.stop_loss_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "stop_loss_type": self.stop_loss_type.value,
            "status": self.status.value,
            "activation_mode": self.activation_mode.value,
            "entry_price": str(self.entry_price),
            "stop_price": str(self.stop_price),
            "current_price": str(self.current_price),
            "highest_price": str(self.highest_price),
            "lowest_price": str(self.lowest_price),
            "stop_percent": self.stop_percent,
            "stop_amount": str(self.stop_amount) if self.stop_amount else None,
            "atr_period": self.atr_period,
            "atr_multiplier": self.atr_multiplier,
            "volatility_window": self.volatility_window,
            "metadata": self.metadata,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class StopLossMetrics:
    """Métriques de stop loss."""
    metric_id: UUID
    stop_loss_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    total_distance: Decimal
    current_distance: Decimal
    max_distance: Decimal
    avg_distance: Decimal
    stop_efficiency: float
    loss_prevented: Decimal
    volatility_adjusted: Optional[float] = None
    effectiveness_score: Optional[float] = None
    efficiency_level: Optional[StopLossEfficiency] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "stop_loss_id": str(self.stop_loss_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id) if self.position_id else None,
            "total_distance": str(self.total_distance),
            "current_distance": str(self.current_distance),
            "max_distance": str(self.max_distance),
            "avg_distance": str(self.avg_distance),
            "stop_efficiency": self.stop_efficiency,
            "loss_prevented": str(self.loss_prevented),
            "volatility_adjusted": self.volatility_adjusted,
            "effectiveness_score": self.effectiveness_score,
            "efficiency_level": self.efficiency_level.value if self.efficiency_level else None,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class StopLossHistory:
    """Historique de stop loss."""
    history_id: UUID
    stop_loss_id: UUID
    user_id: UUID
    position_id: UUID
    timestamp: datetime
    price: Decimal
    stop_price: Decimal
    highest_price: Decimal
    lowest_price: Decimal
    distance: Decimal
    distance_percent: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "history_id": str(self.history_id),
            "stop_loss_id": str(self.stop_loss_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id),
            "timestamp": self.timestamp.isoformat(),
            "price": str(self.price),
            "stop_price": str(self.stop_price),
            "highest_price": str(self.highest_price),
            "lowest_price": str(self.lowest_price),
            "distance": str(self.distance),
            "distance_percent": self.distance_percent,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class StopLossOptimization:
    """Optimisation de stop loss."""
    optimization_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    symbol: str
    stop_loss_type: StopLossType
    parameters: Dict[str, Any]
    performance_score: float
    loss_prevented: Decimal
    trigger_frequency: float
    sharpe_ratio: Optional[float] = None
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
            "stop_loss_type": self.stop_loss_type.value,
            "parameters": self.parameters,
            "performance_score": self.performance_score,
            "loss_prevented": str(self.loss_prevented),
            "trigger_frequency": self.trigger_frequency,
            "sharpe_ratio": self.sharpe_ratio,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_stop_loss(
    position_id: UUID,
    user_id: UUID,
    symbol: str,
    stop_loss_type: StopLossType,
    activation_mode: StopLossActivation,
    entry_price: Decimal,
    stop_price: Decimal,
    current_price: Decimal,
    highest_price: Optional[Decimal] = None,
    lowest_price: Optional[Decimal] = None,
    stop_percent: Optional[float] = None,
    stop_amount: Optional[Decimal] = None,
    atr_period: Optional[int] = None,
    atr_multiplier: Optional[float] = None,
    volatility_window: Optional[int] = None,
    status: StopLossStatus = StopLossStatus.INACTIVE,
    metadata: Optional[Dict] = None
) -> StopLoss:
    """
    Crée un stop loss.

    Args:
        position_id: ID de la position
        user_id: ID de l'utilisateur
        symbol: Symbole
        stop_loss_type: Type de stop loss
        activation_mode: Mode d'activation
        entry_price: Prix d'entrée
        stop_price: Prix du stop
        current_price: Prix actuel
        highest_price: Prix le plus haut
        lowest_price: Prix le plus bas
        stop_percent: Pourcentage de stop
        stop_amount: Montant de stop
        atr_period: Période ATR
        atr_multiplier: Multiplicateur ATR
        volatility_window: Fenêtre de volatilité
        status: Statut
        metadata: Métadonnées

    Returns:
        Stop loss créé
    """
    return StopLoss(
        stop_loss_id=uuid4(),
        position_id=position_id,
        user_id=user_id,
        symbol=symbol,
        stop_loss_type=stop_loss_type,
        status=status,
        activation_mode=activation_mode,
        entry_price=entry_price,
        stop_price=stop_price,
        current_price=current_price,
        highest_price=highest_price or entry_price,
        lowest_price=lowest_price or entry_price,
        stop_percent=stop_percent,
        stop_amount=stop_amount,
        atr_period=atr_period,
        atr_multiplier=atr_multiplier,
        volatility_window=volatility_window,
        metadata=metadata or {}
    )


def create_stop_loss_metrics(
    stop_loss_id: UUID,
    user_id: UUID,
    total_distance: Decimal,
    current_distance: Decimal,
    max_distance: Decimal,
    avg_distance: Decimal,
    stop_efficiency: float,
    loss_prevented: Decimal,
    position_id: Optional[UUID] = None,
    volatility_adjusted: Optional[float] = None,
    effectiveness_score: Optional[float] = None,
    efficiency_level: Optional[StopLossEfficiency] = None,
    metadata: Optional[Dict] = None
) -> StopLossMetrics:
    """
    Crée des métriques de stop loss.

    Args:
        stop_loss_id: ID du stop loss
        user_id: ID de l'utilisateur
        total_distance: Distance totale
        current_distance: Distance actuelle
        max_distance: Distance maximale
        avg_distance: Distance moyenne
        stop_efficiency: Efficacité du stop
        loss_prevented: Perte évitée
        position_id: ID de la position
        volatility_adjusted: Ajusté par volatilité
        effectiveness_score: Score d'efficacité
        efficiency_level: Niveau d'efficacité
        metadata: Métadonnées

    Returns:
        Métriques de stop loss
    """
    return StopLossMetrics(
        metric_id=uuid4(),
        stop_loss_id=stop_loss_id,
        user_id=user_id,
        position_id=position_id,
        total_distance=total_distance,
        current_distance=current_distance,
        max_distance=max_distance,
        avg_distance=avg_distance,
        stop_efficiency=stop_efficiency,
        loss_prevented=loss_prevented,
        volatility_adjusted=volatility_adjusted,
        effectiveness_score=effectiveness_score,
        efficiency_level=efficiency_level,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "StopLossType",
    "StopLossStatus",
    "StopLossActivation",
    "StopLossEfficiency",
    "StopLossModel",
    "StopLossMetricsModel",
    "StopLossHistoryModel",
    "StopLossOptimizationModel",
    "StopLoss",
    "StopLossMetrics",
    "StopLossHistory",
    "StopLossOptimization",
    "create_stop_loss",
    "create_stop_loss_metrics"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de stop loss."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT STOP LOSS MODELS")
    print("=" * 60)

    # Création d'un stop loss
    position_id = UUID("12345678-1234-5678-1234-567812345678")
    user_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'un stop loss...")
    
    stop_loss = create_stop_loss(
        position_id=position_id,
        user_id=user_id,
        symbol="BTC/USDT",
        stop_loss_type=StopLossType.FIXED,
        activation_mode=StopLossActivation.IMMEDIATE,
        entry_price=Decimal("50000"),
        stop_price=Decimal("48000"),
        current_price=Decimal("50000"),
        stop_percent=0.04,
        metadata={"strategy": "swing_trading"}
    )

    print(f"   ID: {stop_loss.stop_loss_id}")
    print(f"   Symbole: {stop_loss.symbol}")
    print(f"   Type: {stop_loss.stop_loss_type.value}")
    print(f"   Entrée: ${stop_loss.entry_price}")
    print(f"   Stop: ${stop_loss.stop_price}")
    print(f"   Statut: {stop_loss.status.value}")

    # Création de métriques
    print(f"\n📈 Création de métriques...")
    
    metrics = create_stop_loss_metrics(
        stop_loss_id=stop_loss.stop_loss_id,
        user_id=user_id,
        total_distance=Decimal("2000"),
        current_distance=Decimal("1000"),
        max_distance=Decimal("2500"),
        avg_distance=Decimal("1500"),
        stop_efficiency=0.75,
        loss_prevented=Decimal("3000"),
        effectiveness_score=0.82,
        efficiency_level=StopLossEfficiency.GOOD
    )

    print(f"   Efficacité: {metrics.stop_efficiency:.2%}")
    print(f"   Perte évitée: ${metrics.loss_prevented}")
    print(f"   Niveau d'efficacité: {metrics.efficiency_level.value}")

    # Historique
    print(f"\n📜 Création d'un historique...")
    
    history = StopLossHistory(
        history_id=uuid4(),
        stop_loss_id=stop_loss.stop_loss_id,
        user_id=user_id,
        position_id=position_id,
        timestamp=datetime.now(),
        price=Decimal("51200"),
        stop_price=Decimal("48500"),
        highest_price=Decimal("51500"),
        lowest_price=Decimal("50000"),
        distance=Decimal("2700"),
        distance_percent=5.4
    )

    print(f"   Prix: ${history.price}")
    print(f"   Stop: ${history.stop_price}")
    print(f"   Distance: ${history.distance}")
    print(f"   Distance %: {history.distance_percent:.1f}%")

    # Optimisation
    print(f"\n🎯 Création d'une optimisation...")
    
    optimization = StopLossOptimization(
        optimization_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        symbol="BTC/USDT",
        stop_loss_type=StopLossType.VOLATILITY,
        parameters={"volatility_multiplier": 1.5, "lookback": 20},
        performance_score=0.92,
        loss_prevented=Decimal("4500"),
        trigger_frequency=0.15,
        sharpe_ratio=1.45
    )

    print(f"   Score de performance: {optimization.performance_score:.2%}")
    print(f"   Perte évitée: ${optimization.loss_prevented}")
    print(f"   Fréquence de déclenchement: {optimization.trigger_frequency:.2%}")

    print("\n" + "=" * 60)
    print("Stop Loss Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
