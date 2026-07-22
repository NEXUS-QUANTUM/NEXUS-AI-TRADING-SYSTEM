"""
NEXUS AI TRADING SYSTEM - HEDGE BOT POSITION MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de position pour le Hedge Bot.
Définition des entités de position, métriques, et états.

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

class PositionStatus(Enum):
    """Statuts de position."""
    OPEN = "open"
    PARTIAL = "partial"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"
    HEDGED = "hedged"
    PENDING = "pending"
    PAUSED = "paused"


class PositionSide(Enum):
    """Côtés de position."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class PositionType(Enum):
    """Types de position."""
    SPOT = "spot"
    FUTURES = "futures"
    OPTIONS = "options"
    PERPETUAL = "perpetual"
    MARGIN = "margin"
    SPREAD = "spread"
    HEDGE = "hedge"
    ARBITRAGE = "arbitrage"


class PositionRisk(Enum):
    """Niveaux de risque de position."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class PositionModel(Base):
    """Modèle de position."""
    __tablename__ = "positions"

    position_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(50), nullable=False)
    side = Column(SQLEnum(PositionSide), nullable=False)
    status = Column(SQLEnum(PositionStatus), nullable=False)
    position_type = Column(SQLEnum(PositionType), nullable=False)
    risk_level = Column(SQLEnum(PositionRisk), nullable=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=True)
    take_profit = Column(Numeric(20, 8), nullable=True)
    liquidation_price = Column(Numeric(20, 8), nullable=True)
    unrealized_pnl = Column(Numeric(20, 8), nullable=True)
    realized_pnl = Column(Numeric(20, 8), nullable=True)
    total_fees = Column(Numeric(20, 8), nullable=False)
    margin_used = Column(Numeric(20, 8), nullable=True)
    leverage = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_positions_user_id", "user_id"),
        Index("idx_positions_symbol", "symbol"),
        Index("idx_positions_exchange", "exchange"),
        Index("idx_positions_status", "status"),
        Index("idx_positions_side", "side"),
        Index("idx_positions_type", "position_type"),
        Index("idx_positions_opened_at", "opened_at"),
    )


class PositionMetricsModel(Base):
    """Modèle de métriques de position."""
    __tablename__ = "position_metrics"

    metric_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), ForeignKey("positions.position_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    total_pnl = Column(Numeric(20, 8), nullable=False)
    total_pnl_usd = Column(Numeric(20, 8), nullable=False)
    max_pnl = Column(Numeric(20, 8), nullable=False)
    min_pnl = Column(Numeric(20, 8), nullable=False)
    average_pnl = Column(Numeric(20, 8), nullable=False)
    max_drawdown = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=False)
    sortino_ratio = Column(Float, nullable=False)
    calmar_ratio = Column(Float, nullable=False)
    win_rate = Column(Float, nullable=False)
    profit_factor = Column(Float, nullable=False)
    holding_period = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    position = relationship("PositionModel")

    __table_args__ = (
        Index("idx_position_metrics_position_id", "position_id"),
        Index("idx_position_metrics_user_id", "user_id"),
        Index("idx_position_metrics_calculated_at", "calculated_at"),
    )


class PositionHistoryModel(Base):
    """Modèle d'historique de position."""
    __tablename__ = "position_history"

    history_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), ForeignKey("positions.position_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    unrealized_pnl = Column(Numeric(20, 8), nullable=True)
    realized_pnl = Column(Numeric(20, 8), nullable=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

    # Relations
    position = relationship("PositionModel")

    __table_args__ = (
        Index("idx_position_history_position_id", "position_id"),
        Index("idx_position_history_user_id", "user_id"),
        Index("idx_position_history_timestamp", "timestamp"),
    )


class PositionRiskModel(Base):
    """Modèle de risque de position."""
    __tablename__ = "position_risks"

    risk_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), ForeignKey("positions.position_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(SQLEnum(PositionRisk), nullable=False)
    var_95 = Column(Numeric(20, 8), nullable=False)
    var_99 = Column(Numeric(20, 8), nullable=False)
    expected_shortfall = Column(Numeric(20, 8), nullable=False)
    max_loss = Column(Numeric(20, 8), nullable=False)
    probability_of_loss = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    position = relationship("PositionModel")

    __table_args__ = (
        Index("idx_position_risks_position_id", "position_id"),
        Index("idx_position_risks_user_id", "user_id"),
        Index("idx_position_risks_calculated_at", "calculated_at"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class Position:
    """Position."""
    position_id: UUID
    user_id: UUID
    symbol: str
    exchange: str
    side: PositionSide
    status: PositionStatus
    position_type: PositionType
    risk_level: Optional[PositionRisk]
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    stop_loss: Optional[Decimal]
    take_profit: Optional[Decimal]
    liquidation_price: Optional[Decimal]
    unrealized_pnl: Optional[Decimal]
    realized_pnl: Optional[Decimal]
    total_fees: Decimal
    margin_used: Optional[Decimal]
    leverage: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value,
            "status": self.status.value,
            "position_type": self.position_type.value,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "quantity": str(self.quantity),
            "entry_price": str(self.entry_price),
            "current_price": str(self.current_price),
            "stop_loss": str(self.stop_loss) if self.stop_loss else None,
            "take_profit": str(self.take_profit) if self.take_profit else None,
            "liquidation_price": str(self.liquidation_price) if self.liquidation_price else None,
            "unrealized_pnl": str(self.unrealized_pnl) if self.unrealized_pnl else None,
            "realized_pnl": str(self.realized_pnl) if self.realized_pnl else None,
            "total_fees": str(self.total_fees),
            "margin_used": str(self.margin_used) if self.margin_used else None,
            "leverage": self.leverage,
            "metadata": self.metadata,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class PositionMetrics:
    """Métriques de position."""
    metric_id: UUID
    position_id: UUID
    user_id: UUID
    total_pnl: Decimal
    total_pnl_usd: Decimal
    max_pnl: Decimal
    min_pnl: Decimal
    average_pnl: Decimal
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    holding_period: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "total_pnl": str(self.total_pnl),
            "total_pnl_usd": str(self.total_pnl_usd),
            "max_pnl": str(self.max_pnl),
            "min_pnl": str(self.min_pnl),
            "average_pnl": str(self.average_pnl),
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "holding_period": self.holding_period,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class PositionHistory:
    """Historique de position."""
    history_id: UUID
    position_id: UUID
    user_id: UUID
    timestamp: datetime
    price: Decimal
    unrealized_pnl: Optional[Decimal]
    realized_pnl: Optional[Decimal]
    quantity: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "history_id": str(self.history_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "timestamp": self.timestamp.isoformat(),
            "price": str(self.price),
            "unrealized_pnl": str(self.unrealized_pnl) if self.unrealized_pnl else None,
            "realized_pnl": str(self.realized_pnl) if self.realized_pnl else None,
            "quantity": str(self.quantity),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class PositionRisk:
    """Risque de position."""
    risk_id: UUID
    position_id: UUID
    user_id: UUID
    risk_score: float
    risk_level: PositionRisk
    var_95: Decimal
    var_99: Decimal
    expected_shortfall: Decimal
    max_loss: Decimal
    probability_of_loss: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "risk_id": str(self.risk_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "var_95": str(self.var_95),
            "var_99": str(self.var_99),
            "expected_shortfall": str(self.expected_shortfall),
            "max_loss": str(self.max_loss),
            "probability_of_loss": self.probability_of_loss,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_position(
    user_id: UUID,
    symbol: str,
    exchange: str,
    side: PositionSide,
    position_type: PositionType,
    quantity: Decimal,
    entry_price: Decimal,
    current_price: Decimal,
    status: PositionStatus = PositionStatus.OPEN,
    stop_loss: Optional[Decimal] = None,
    take_profit: Optional[Decimal] = None,
    liquidation_price: Optional[Decimal] = None,
    margin_used: Optional[Decimal] = None,
    leverage: Optional[float] = None,
    metadata: Optional[Dict] = None
) -> Position:
    """
    Crée une position.

    Args:
        user_id: ID de l'utilisateur
        symbol: Symbole
        exchange: Exchange
        side: Côté
        position_type: Type de position
        quantity: Quantité
        entry_price: Prix d'entrée
        current_price: Prix actuel
        status: Statut
        stop_loss: Stop loss
        take_profit: Take profit
        liquidation_price: Prix de liquidation
        margin_used: Marge utilisée
        leverage: Effet de levier
        metadata: Métadonnées

    Returns:
        Position créée
    """
    return Position(
        position_id=uuid4(),
        user_id=user_id,
        symbol=symbol,
        exchange=exchange,
        side=side,
        status=status,
        position_type=position_type,
        risk_level=None,
        quantity=quantity,
        entry_price=entry_price,
        current_price=current_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        liquidation_price=liquidation_price,
        unrealized_pnl=None,
        realized_pnl=None,
        total_fees=Decimal("0"),
        margin_used=margin_used,
        leverage=leverage,
        metadata=metadata or {}
    )


def create_position_metrics(
    position_id: UUID,
    user_id: UUID,
    total_pnl: Decimal,
    total_pnl_usd: Decimal,
    max_pnl: Decimal,
    min_pnl: Decimal,
    average_pnl: Decimal,
    max_drawdown: float,
    sharpe_ratio: float,
    sortino_ratio: float,
    calmar_ratio: float,
    win_rate: float,
    profit_factor: float,
    holding_period: float,
    metadata: Optional[Dict] = None
) -> PositionMetrics:
    """
    Crée des métriques de position.

    Args:
        position_id: ID de la position
        user_id: ID de l'utilisateur
        total_pnl: PnL total
        total_pnl_usd: PnL total en USD
        max_pnl: PnL maximum
        min_pnl: PnL minimum
        average_pnl: PnL moyen
        max_drawdown: Drawdown maximum
        sharpe_ratio: Sharpe Ratio
        sortino_ratio: Sortino Ratio
        calmar_ratio: Calmar Ratio
        win_rate: Taux de victoire
        profit_factor: Facteur de profit
        holding_period: Période de détention
        metadata: Métadonnées

    Returns:
        Métriques de position
    """
    return PositionMetrics(
        metric_id=uuid4(),
        position_id=position_id,
        user_id=user_id,
        total_pnl=total_pnl,
        total_pnl_usd=total_pnl_usd,
        max_pnl=max_pnl,
        min_pnl=min_pnl,
        average_pnl=average_pnl,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
        win_rate=win_rate,
        profit_factor=profit_factor,
        holding_period=holding_period,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PositionStatus",
    "PositionSide",
    "PositionType",
    "PositionRisk",
    "PositionModel",
    "PositionMetricsModel",
    "PositionHistoryModel",
    "PositionRiskModel",
    "Position",
    "PositionMetrics",
    "PositionHistory",
    "PositionRisk",
    "create_position",
    "create_position_metrics"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de position."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT POSITION MODELS")
    print("=" * 60)

    # Création d'une position
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Création d'une position...")
    
    position = create_position(
        user_id=user_id,
        symbol="BTC/USDT",
        exchange="BINANCE",
        side=PositionSide.LONG,
        position_type=PositionType.SPOT,
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000"),
        current_price=Decimal("52000"),
        stop_loss=Decimal("48000"),
        take_profit=Decimal("55000"),
        leverage=1.0,
        metadata={"strategy": "swing_trading"}
    )

    print(f"   ID: {position.position_id}")
    print(f"   Symbole: {position.symbol}")
    print(f"   Côté: {position.side.value}")
    print(f"   Entrée: ${position.entry_price}")
    print(f"   Actuel: ${position.current_price}")
    print(f"   Quantité: {position.quantity}")

    # Métriques de position
    print(f"\n📈 Métriques de position:")
    
    metrics = create_position_metrics(
        position_id=position.position_id,
        user_id=user_id,
        total_pnl=Decimal("200"),
        total_pnl_usd=Decimal("200"),
        max_pnl=Decimal("350"),
        min_pnl=Decimal("-150"),
        average_pnl=Decimal("75"),
        max_drawdown=0.12,
        sharpe_ratio=1.45,
        sortino_ratio=1.20,
        calmar_ratio=0.85,
        win_rate=0.68,
        profit_factor=1.75,
        holding_period=72.5
    )

    print(f"   PnL total: ${metrics.total_pnl}")
    print(f"   Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"   Win rate: {metrics.win_rate*100:.1f}%")
    print(f"   Période de détention: {metrics.holding_period:.1f}h")

    # Risque de position
    print(f"\n⚠️ Risque de position:")
    
    risk = PositionRisk(
        risk_id=uuid4(),
        position_id=position.position_id,
        user_id=user_id,
        risk_score=35.5,
        risk_level=PositionRisk.MEDIUM,
        var_95=Decimal("2500"),
        var_99=Decimal("5000"),
        expected_shortfall=Decimal("3500"),
        max_loss=Decimal("10000"),
        probability_of_loss=0.25
    )

    print(f"   Score de risque: {risk.risk_score:.1f}")
    print(f"   Niveau: {risk.risk_level.value}")
    print(f"   VaR 95%: ${risk.var_95}")
    print(f"   Probabilité de perte: {risk.probability_of_loss:.1%}")

    # Historique
    print(f"\n📜 Historique de la position:")
    
    history = PositionHistory(
        history_id=uuid4(),
        position_id=position.position_id,
        user_id=user_id,
        timestamp=datetime.now() - timedelta(days=1),
        price=Decimal("51000"),
        unrealized_pnl=Decimal("100"),
        realized_pnl=Decimal("0"),
        quantity=Decimal("0.1")
    )

    print(f"   Prix: ${history.price}")
    print(f"   PnL non réalisé: ${history.unrealized_pnl}")

    print("\n" + "=" * 60)
    print("Position Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
