"""
NEXUS AI TRADING SYSTEM - HEDGE BOT TRAILING STOP MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de trailing stop pour le Hedge Bot.
Définition des entités de trailing stop, métriques, et historiques.

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

class TrailingStopType(Enum):
    """Types de trailing stop."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    VOLATILITY = "volatility"
    ATR = "atr"
    DYNAMIC = "dynamic"
    SMART = "smart"
    ADAPTIVE = "adaptive"
    HYBRID = "hybrid"


class TrailingStopStatus(Enum):
    """Statuts de trailing stop."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAUSED = "paused"


class TrailingStopActivation(Enum):
    """Modes d'activation de trailing stop."""
    IMMEDIATE = "immediate"
    AT_PRICE = "at_price"
    AFTER_PROFIT = "after_profit"
    ON_BREAKOUT = "on_breakout"
    ON_VOLATILITY = "on_volatility"


class TrailingStopEfficiency(Enum):
    """Niveaux d'efficacité de trailing stop."""
    POOR = "poor"
    AVERAGE = "average"
    GOOD = "good"
    EXCELLENT = "excellent"
    PERFECT = "perfect"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class TrailingStopModel(Base):
    """Modèle de trailing stop."""
    __tablename__ = "trailing_stops"

    stop_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    stop_type = Column(SQLEnum(TrailingStopType), nullable=False)
    status = Column(SQLEnum(TrailingStopStatus), nullable=False)
    activation_mode = Column(SQLEnum(TrailingStopActivation), nullable=False)
    initial_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=False)
    highest_price = Column(Numeric(20, 8), nullable=False)
    lowest_price = Column(Numeric(20, 8), nullable=False)
    stop_price = Column(Numeric(20, 8), nullable=False)
    activation_price = Column(Numeric(20, 8), nullable=True)
    trail_percent = Column(Float, nullable=True)
    trail_amount = Column(Numeric(20, 8), nullable=True)
    atr_period = Column(Integer, nullable=True)
    atr_multiplier = Column(Float, nullable=True)
    volatility_window = Column(Integer, nullable=True)
    metadata = Column(JSON, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_trailing_stops_user_id", "user_id"),
        Index("idx_trailing_stops_position_id", "position_id"),
        Index("idx_trailing_stops_symbol", "symbol"),
        Index("idx_trailing_stops_status", "status"),
        Index("idx_trailing_stops_type", "stop_type"),
        Index("idx_trailing_stops_created_at", "created_at"),
    )


class TrailingStopMetricsModel(Base):
    """Modèle de métriques de trailing stop."""
    __tablename__ = "trailing_stop_metrics"

    metric_id = Column(String(36), primary_key=True)
    stop_id = Column(String(36), ForeignKey("trailing_stops.stop_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=False)
    total_distance = Column(Numeric(20, 8), nullable=False)
    current_distance = Column(Numeric(20, 8), nullable=False)
    max_distance = Column(Numeric(20, 8), nullable=False)
    avg_distance = Column(Numeric(20, 8), nullable=False)
    stop_efficiency = Column(Float, nullable=False)
    profit_protected = Column(Numeric(20, 8), nullable=False)
    volatility_adjusted = Column(Float, nullable=True)
    effectiveness_score = Column(Float, nullable=True)
    efficiency_level = Column(SQLEnum(TrailingStopEfficiency), nullable=True)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    stop = relationship("TrailingStopModel")

    __table_args__ = (
        Index("idx_trailing_stop_metrics_user_id", "user_id"),
        Index("idx_trailing_stop_metrics_stop_id", "stop_id"),
        Index("idx_trailing_stop_metrics_position_id", "position_id"),
        Index("idx_trailing_stop_metrics_calculated_at", "calculated_at"),
    )


class TrailingStopHistoryModel(Base):
    """Modèle d'historique de trailing stop."""
    __tablename__ = "trailing_stop_history"

    history_id = Column(String(36), primary_key=True)
    stop_id = Column(String(36), ForeignKey("trailing_stops.stop_id"), nullable=False)
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
    stop = relationship("TrailingStopModel")

    __table_args__ = (
        Index("idx_trailing_stop_history_stop_id", "stop_id"),
        Index("idx_trailing_stop_history_user_id", "user_id"),
        Index("idx_trailing_stop_history_timestamp", "timestamp"),
    )


class TrailingStopOptimizationModel(Base):
    """Modèle d'optimisation de trailing stop."""
    __tablename__ = "trailing_stop_optimizations"

    optimization_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    stop_type = Column(SQLEnum(TrailingStopType), nullable=False)
    parameters = Column(JSON, nullable=False)
    performance_score = Column(Float, nullable=False)
    profit_protected = Column(Numeric(20, 8), nullable=False)
    trigger_frequency = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_trailing_stop_optimizations_user_id", "user_id"),
        Index("idx_trailing_stop_optimizations_position_id", "position_id"),
        Index("idx_trailing_stop_optimizations_symbol", "symbol"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class TrailingStop:
    """Trailing stop."""
    stop_id: UUID
    position_id: UUID
    user_id: UUID
    symbol: str
    stop_type: TrailingStopType
    status: TrailingStopStatus
    activation_mode: TrailingStopActivation
    initial_price: Decimal
    current_price: Decimal
    highest_price: Decimal
    lowest_price: Decimal
    stop_price: Decimal
    activation_price: Optional[Decimal] = None
    trail_percent: Optional[float] = None
    trail_amount: Optional[Decimal] = None
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
            "stop_id": str(self.stop_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "stop_type": self.stop_type.value,
            "status": self.status.value,
            "activation_mode": self.activation_mode.value,
            "initial_price": str(self.initial_price),
            "current_price": str(self.current_price),
            "highest_price": str(self.highest_price),
            "lowest_price": str(self.lowest_price),
            "stop_price": str(self.stop_price),
            "activation_price": str(self.activation_price) if self.activation_price else None,
            "trail_percent": self.trail_percent,
            "trail_amount": str(self.trail_amount) if self.trail_amount else None,
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
class TrailingStopMetrics:
    """Métriques de trailing stop."""
    metric_id: UUID
    stop_id: UUID
    user_id: UUID
    position_id: UUID
    total_distance: Decimal
    current_distance: Decimal
    max_distance: Decimal
    avg_distance: Decimal
    stop_efficiency: float
    profit_protected: Decimal
    volatility_adjusted: Optional[float] = None
    effectiveness_score: Optional[float] = None
    efficiency_level: Optional[TrailingStopEfficiency] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "stop_id": str(self.stop_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id),
            "total_distance": str(self.total_distance),
            "current_distance": str(self.current_distance),
            "max_distance": str(self.max_distance),
            "avg_distance": str(self.avg_distance),
            "stop_efficiency": self.stop_efficiency,
            "profit_protected": str(self.profit_protected),
            "volatility_adjusted": self.volatility_adjusted,
            "effectiveness_score": self.effectiveness_score,
            "efficiency_level": self.efficiency_level.value if self.efficiency_level else None,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class TrailingStopHistory:
    """Historique de trailing stop."""
    history_id: UUID
    stop_id: UUID
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
            "stop_id": str(self.stop_id),
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
class TrailingStopOptimization:
    """Optimisation de trailing stop."""
    optimization_id: UUID
    user_id: UUID
    position_id: UUID
    symbol: str
    stop_type: TrailingStopType
    parameters: Dict[str, Any]
    performance_score: float
    profit_protected: Decimal
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
            "position_id": str(self.position_id),
            "symbol": self.symbol,
            "stop_type": self.stop_type.value,
            "parameters": self.parameters,
            "performance_score": self.performance_score,
            "profit_protected": str(self.profit_protected),
            "trigger_frequency": self.trigger_frequency,
            "sharpe_ratio": self.sharpe_ratio,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_trailing_stop(
    position_id: UUID,
    user_id: UUID,
    symbol: str,
    stop_type: TrailingStopType,
    activation_mode: TrailingStopActivation,
    initial_price: Decimal,
    current_price: Decimal,
    stop_price: Decimal,
    highest_price: Optional[Decimal] = None,
    lowest_price: Optional[Decimal] = None,
    activation_price: Optional[Decimal] = None,
    trail_percent: Optional[float] = None,
    trail_amount: Optional[Decimal] = None,
    atr_period: Optional[int] = None,
    atr_multiplier: Optional[float] = None,
    volatility_window: Optional[int] = None,
    metadata: Optional[Dict] = None
) -> TrailingStop:
    """
    Crée un trailing stop.

    Args:
        position_id: ID de la position
        user_id: ID de l'utilisateur
        symbol: Symbole
        stop_type: Type de trailing stop
        activation_mode: Mode d'activation
        initial_price: Prix initial
        current_price: Prix actuel
        stop_price: Prix du stop
        highest_price: Prix le plus haut
        lowest_price: Prix le plus bas
        activation_price: Prix d'activation
        trail_percent: Pourcentage de suivi
        trail_amount: Montant de suivi
        atr_period: Période ATR
        atr_multiplier: Multiplicateur ATR
        volatility_window: Fenêtre de volatilité
        metadata: Métadonnées

    Returns:
        Trailing stop créé
    """
    return TrailingStop(
        stop_id=uuid4(),
        position_id=position_id,
        user_id=user_id,
        symbol=symbol,
        stop_type=stop_type,
        status=TrailingStopStatus.INACTIVE,
        activation_mode=activation_mode,
        initial_price=initial_price,
        current_price=current_price,
        highest_price=highest_price or initial_price,
        lowest_price=lowest_price or initial_price,
        stop_price=stop_price,
        activation_price=activation_price,
        trail_percent=trail_percent,
        trail_amount=trail_amount,
        atr_period=atr_period,
        atr_multiplier=atr_multiplier,
        volatility_window=volatility_window,
        metadata=metadata or {}
    )


def create_trailing_stop_metrics(
    stop_id: UUID,
    user_id: UUID,
    position_id: UUID,
    total_distance: Decimal,
    current_distance: Decimal,
    max_distance: Decimal,
    avg_distance: Decimal,
    stop_efficiency: float,
    profit_protected: Decimal,
    volatility_adjusted: Optional[float] = None,
    effectiveness_score: Optional[float] = None,
    efficiency_level: Optional[TrailingStopEfficiency] = None,
    metadata: Optional[Dict] = None
) -> TrailingStopMetrics:
    """
    Crée des métriques de trailing stop.

    Args:
        stop_id: ID du stop
        user_id: ID de l'utilisateur
        position_id: ID de la position
        total_distance: Distance totale
        current_distance: Distance actuelle
        max_distance: Distance maximale
        avg_distance: Distance moyenne
        stop_efficiency: Efficacité du stop
        profit_protected: Profit protégé
        volatility_adjusted: Ajusté par volatilité
        effectiveness_score: Score d'efficacité
        efficiency_level: Niveau d'efficacité
        metadata: Métadonnées

    Returns:
        Métriques de trailing stop
    """
    return TrailingStopMetrics(
        metric_id=uuid4(),
        stop_id=stop_id,
        user_id=user_id,
        position_id=position_id,
        total_distance=total_distance,
        current_distance=current_distance,
        max_distance=max_distance,
        avg_distance=avg_distance,
        stop_efficiency=stop_efficiency,
        profit_protected=profit_protected,
        volatility_adjusted=volatility_adjusted,
        effectiveness_score=effectiveness_score,
        efficiency_level=efficiency_level,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TrailingStopType",
    "TrailingStopStatus",
    "TrailingStopActivation",
    "TrailingStopEfficiency",
    "TrailingStopModel",
    "TrailingStopMetricsModel",
    "TrailingStopHistoryModel",
    "TrailingStopOptimizationModel",
    "TrailingStop",
    "TrailingStopMetrics",
    "TrailingStopHistory",
    "TrailingStopOptimization",
    "create_trailing_stop",
    "create_trailing_stop_metrics"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de trailing stop."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT TRAILING STOP MODELS")
    print("=" * 60)

    # Création d'un trailing stop
    position_id = UUID("12345678-1234-5678-1234-567812345678")
    user_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'un trailing stop...")
    
    stop = create_trailing_stop(
        position_id=position_id,
        user_id=user_id,
        symbol="BTC/USDT",
        stop_type=TrailingStopType.PERCENTAGE,
        activation_mode=TrailingStopActivation.AFTER_PROFIT,
        initial_price=Decimal("50000"),
        current_price=Decimal("50000"),
        stop_price=Decimal("49000"),
        activation_price=Decimal("51000"),
        trail_percent=0.02,
        metadata={"strategy": "swing_trading"}
    )

    print(f"   ID: {stop.stop_id}")
    print(f"   Symbole: {stop.symbol}")
    print(f"   Type: {stop.stop_type.value}")
    print(f"   Prix initial: ${stop.initial_price}")
    print(f"   Stop price: ${stop.stop_price}")
    print(f"   Statut: {stop.status.value}")

    # Création de métriques
    print(f"\n📈 Création de métriques...")
    
    metrics = create_trailing_stop_metrics(
        stop_id=stop.stop_id,
        user_id=user_id,
        position_id=position_id,
        total_distance=Decimal("1500"),
        current_distance=Decimal("800"),
        max_distance=Decimal("2000"),
        avg_distance=Decimal("1200"),
        stop_efficiency=0.75,
        profit_protected=Decimal("500"),
        effectiveness_score=0.82,
        efficiency_level=TrailingStopEfficiency.GOOD
    )

    print(f"   Efficacité: {metrics.stop_efficiency:.2%}")
    print(f"   Profit protégé: ${metrics.profit_protected}")
    print(f"   Niveau d'efficacité: {metrics.efficiency_level.value}")

    # Historique
    print(f"\n📜 Création d'un historique...")
    
    history = TrailingStopHistory(
        history_id=uuid4(),
        stop_id=stop.stop_id,
        user_id=user_id,
        position_id=position_id,
        timestamp=datetime.now(),
        price=Decimal("51200"),
        stop_price=Decimal("50176"),
        highest_price=Decimal("51500"),
        lowest_price=Decimal("50000"),
        distance=Decimal("1024"),
        distance_percent=2.0
    )

    print(f"   Prix: ${history.price}")
    print(f"   Stop: ${history.stop_price}")
    print(f"   Distance: ${history.distance}")
    print(f"   Distance %: {history.distance_percent:.1f}%")

    # Optimisation
    print(f"\n🎯 Création d'une optimisation...")
    
    optimization = TrailingStopOptimization(
        optimization_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        symbol="BTC/USDT",
        stop_type=TrailingStopType.PERCENTAGE,
        parameters={"trail_percent": 0.025, "activation": 0.03},
        performance_score=0.92,
        profit_protected=Decimal("750"),
        trigger_frequency=0.15,
        sharpe_ratio=1.45
    )

    print(f"   Score de performance: {optimization.performance_score:.2%}")
    print(f"   Profit protégé: ${optimization.profit_protected}")
    print(f"   Fréquence de déclenchement: {optimization.trigger_frequency:.2%}")

    print("\n" + "=" * 60)
    print("Trailing Stop Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
