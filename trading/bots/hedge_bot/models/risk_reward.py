"""
NEXUS AI TRADING SYSTEM - HEDGE BOT RISK-REWARD MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de risque-récompense pour le Hedge Bot.
Définition des entités de risque, récompense, ratios, et métriques associées.

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

class RiskRewardType(Enum):
    """Types de risque-récompense."""
    STATIC = "static"
    DYNAMIC = "dynamic"
    ADAPTIVE = "adaptive"
    FIXED_RATIO = "fixed_ratio"
    VARIABLE_RATIO = "variable_ratio"
    KELLY = "kelly"
    OPTIMAL = "optimal"


class RiskRewardStatus(Enum):
    """Statuts de risque-récompense."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    UPDATED = "updated"
    CALCULATED = "calculated"
    OPTIMIZED = "optimized"


class RiskRewardLevel(Enum):
    """Niveaux de risque-récompense."""
    VERY_CONSERVATIVE = "very_conservative"
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class RiskRewardModel(Base):
    """Modèle de risque-récompense."""
    __tablename__ = "risk_rewards"

    risk_reward_id = Column(String(36), primary_key=True)
    position_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    risk_reward_type = Column(SQLEnum(RiskRewardType), nullable=False)
    status = Column(SQLEnum(RiskRewardStatus), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=False)
    take_profit = Column(Numeric(20, 8), nullable=False)
    risk_amount = Column(Numeric(20, 8), nullable=False)
    reward_amount = Column(Numeric(20, 8), nullable=False)
    risk_reward_ratio = Column(Float, nullable=False)
    position_size = Column(Numeric(20, 8), nullable=False)
    risk_percent = Column(Float, nullable=False)
    reward_percent = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_risk_rewards_user_id", "user_id"),
        Index("idx_risk_rewards_position_id", "position_id"),
        Index("idx_risk_rewards_symbol", "symbol"),
        Index("idx_risk_rewards_type", "risk_reward_type"),
        Index("idx_risk_rewards_status", "status"),
        Index("idx_risk_rewards_calculated_at", "calculated_at"),
    )


class RiskRewardMetricsModel(Base):
    """Modèle de métriques de risque-récompense."""
    __tablename__ = "risk_reward_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=False)
    average_risk_reward = Column(Float, nullable=False)
    max_risk_reward = Column(Float, nullable=False)
    min_risk_reward = Column(Float, nullable=False)
    median_risk_reward = Column(Float, nullable=False)
    total_risk = Column(Numeric(20, 8), nullable=False)
    total_reward = Column(Numeric(20, 8), nullable=False)
    success_rate = Column(Float, nullable=False)
    expected_value = Column(Numeric(20, 8), nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_risk_reward_metrics_user_id", "user_id"),
        Index("idx_risk_reward_metrics_position_id", "position_id"),
        Index("idx_risk_reward_metrics_calculated_at", "calculated_at"),
    )


class RiskRewardOptimizationModel(Base):
    """Modèle d'optimisation de risque-récompense."""
    __tablename__ = "risk_reward_optimizations"

    optimization_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    optimal_stop_loss = Column(Numeric(20, 8), nullable=False)
    optimal_take_profit = Column(Numeric(20, 8), nullable=False)
    optimal_risk_reward = Column(Float, nullable=False)
    optimal_position_size = Column(Numeric(20, 8), nullable=False)
    expected_return = Column(Numeric(20, 8), nullable=False)
    sharpe_ratio = Column(Float, nullable=False)
    kelly_fraction = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_risk_reward_optimizations_user_id", "user_id"),
        Index("idx_risk_reward_optimizations_symbol", "symbol"),
        Index("idx_risk_reward_optimizations_calculated_at", "calculated_at"),
    )


class KellyCriterionModel(Base):
    """Modèle de critère de Kelly."""
    __tablename__ = "kelly_criteria"

    kelly_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    win_rate = Column(Float, nullable=False)
    average_win = Column(Numeric(20, 8), nullable=False)
    average_loss = Column(Numeric(20, 8), nullable=False)
    kelly_fraction = Column(Float, nullable=False)
    optimal_fraction = Column(Float, nullable=False)
    half_kelly = Column(Float, nullable=False)
    quarter_kelly = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_kelly_criteria_user_id", "user_id"),
        Index("idx_kelly_criteria_symbol", "symbol"),
        Index("idx_kelly_criteria_calculated_at", "calculated_at"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class RiskReward:
    """Risque-récompense."""
    risk_reward_id: UUID
    position_id: UUID
    user_id: UUID
    symbol: str
    risk_reward_type: RiskRewardType
    status: RiskRewardStatus
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    risk_amount: Decimal
    reward_amount: Decimal
    risk_reward_ratio: float
    position_size: Decimal
    risk_percent: float
    reward_percent: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "risk_reward_id": str(self.risk_reward_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "risk_reward_type": self.risk_reward_type.value,
            "status": self.status.value,
            "entry_price": str(self.entry_price),
            "stop_loss": str(self.stop_loss),
            "take_profit": str(self.take_profit),
            "risk_amount": str(self.risk_amount),
            "reward_amount": str(self.reward_amount),
            "risk_reward_ratio": self.risk_reward_ratio,
            "position_size": str(self.position_size),
            "risk_percent": self.risk_percent,
            "reward_percent": self.reward_percent,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class RiskRewardMetrics:
    """Métriques de risque-récompense."""
    metric_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    average_risk_reward: float
    max_risk_reward: float
    min_risk_reward: float
    median_risk_reward: float
    total_risk: Decimal
    total_reward: Decimal
    success_rate: float
    expected_value: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id) if self.position_id else None,
            "average_risk_reward": self.average_risk_reward,
            "max_risk_reward": self.max_risk_reward,
            "min_risk_reward": self.min_risk_reward,
            "median_risk_reward": self.median_risk_reward,
            "total_risk": str(self.total_risk),
            "total_reward": str(self.total_reward),
            "success_rate": self.success_rate,
            "expected_value": str(self.expected_value),
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class RiskRewardOptimization:
    """Optimisation de risque-récompense."""
    optimization_id: UUID
    user_id: UUID
    symbol: str
    optimal_stop_loss: Decimal
    optimal_take_profit: Decimal
    optimal_risk_reward: float
    optimal_position_size: Decimal
    expected_return: Decimal
    sharpe_ratio: float
    kelly_fraction: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "optimization_id": str(self.optimization_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "optimal_stop_loss": str(self.optimal_stop_loss),
            "optimal_take_profit": str(self.optimal_take_profit),
            "optimal_risk_reward": self.optimal_risk_reward,
            "optimal_position_size": str(self.optimal_position_size),
            "expected_return": str(self.expected_return),
            "sharpe_ratio": self.sharpe_ratio,
            "kelly_fraction": self.kelly_fraction,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class KellyCriterion:
    """Critère de Kelly."""
    kelly_id: UUID
    user_id: UUID
    symbol: str
    win_rate: float
    average_win: Decimal
    average_loss: Decimal
    kelly_fraction: float
    optimal_fraction: float
    half_kelly: float
    quarter_kelly: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "kelly_id": str(self.kelly_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "win_rate": self.win_rate,
            "average_win": str(self.average_win),
            "average_loss": str(self.average_loss),
            "kelly_fraction": self.kelly_fraction,
            "optimal_fraction": self.optimal_fraction,
            "half_kelly": self.half_kelly,
            "quarter_kelly": self.quarter_kelly,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_risk_reward(
    position_id: UUID,
    user_id: UUID,
    symbol: str,
    entry_price: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
    position_size: Decimal,
    risk_reward_type: RiskRewardType = RiskRewardType.STATIC,
    metadata: Optional[Dict] = None
) -> RiskReward:
    """
    Crée une entité risque-récompense.

    Args:
        position_id: ID de la position
        user_id: ID de l'utilisateur
        symbol: Symbole
        entry_price: Prix d'entrée
        stop_loss: Stop loss
        take_profit: Take profit
        position_size: Taille de la position
        risk_reward_type: Type de risque-récompense
        metadata: Métadonnées

    Returns:
        Entité risque-récompense
    """
    risk_amount = abs(entry_price - stop_loss) * position_size
    reward_amount = abs(take_profit - entry_price) * position_size
    risk_reward_ratio = float(reward_amount / risk_amount) if risk_amount > 0 else 0
    risk_percent = float(risk_amount / (entry_price * position_size) * 100) if entry_price > 0 else 0
    reward_percent = float(reward_amount / (entry_price * position_size) * 100) if entry_price > 0 else 0

    return RiskReward(
        risk_reward_id=uuid4(),
        position_id=position_id,
        user_id=user_id,
        symbol=symbol,
        risk_reward_type=risk_reward_type,
        status=RiskRewardStatus.CALCULATED,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_amount=risk_amount,
        reward_amount=reward_amount,
        risk_reward_ratio=risk_reward_ratio,
        position_size=position_size,
        risk_percent=risk_percent,
        reward_percent=reward_percent,
        metadata=metadata or {}
    )


def create_kelly_criterion(
    user_id: UUID,
    symbol: str,
    win_rate: float,
    average_win: Decimal,
    average_loss: Decimal,
    metadata: Optional[Dict] = None
) -> KellyCriterion:
    """
    Crée un critère de Kelly.

    Args:
        user_id: ID de l'utilisateur
        symbol: Symbole
        win_rate: Taux de victoire
        average_win: Victoire moyenne
        average_loss: Perte moyenne
        metadata: Métadonnées

    Returns:
        Critère de Kelly
    """
    kelly_fraction = (win_rate - (1 - win_rate) / (float(average_win / average_loss))) if average_loss > 0 else 0
    optimal_fraction = max(0, min(1, kelly_fraction))
    half_kelly = optimal_fraction * 0.5
    quarter_kelly = optimal_fraction * 0.25

    return KellyCriterion(
        kelly_id=uuid4(),
        user_id=user_id,
        symbol=symbol,
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
        kelly_fraction=kelly_fraction,
        optimal_fraction=optimal_fraction,
        half_kelly=half_kelly,
        quarter_kelly=quarter_kelly,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "RiskRewardType",
    "RiskRewardStatus",
    "RiskRewardLevel",
    "RiskRewardModel",
    "RiskRewardMetricsModel",
    "RiskRewardOptimizationModel",
    "KellyCriterionModel",
    "RiskReward",
    "RiskRewardMetrics",
    "RiskRewardOptimization",
    "KellyCriterion",
    "create_risk_reward",
    "create_kelly_criterion"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de risque-récompense."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT RISK-REWARD MODELS")
    print("=" * 60)

    # Création d'une entité risque-récompense
    position_id = UUID("12345678-1234-5678-1234-567812345678")
    user_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'une entité risque-récompense...")
    
    risk_reward = create_risk_reward(
        position_id=position_id,
        user_id=user_id,
        symbol="BTC/USDT",
        entry_price=Decimal("50000"),
        stop_loss=Decimal("48000"),
        take_profit=Decimal("52500"),
        position_size=Decimal("0.1"),
        risk_reward_type=RiskRewardType.STATIC,
        metadata={"strategy": "swing_trading"}
    )

    print(f"   ID: {risk_reward.risk_reward_id}")
    print(f"   Entry: ${risk_reward.entry_price}")
    print(f"   Stop Loss: ${risk_reward.stop_loss}")
    print(f"   Take Profit: ${risk_reward.take_profit}")
    print(f"   Risk: ${risk_reward.risk_amount}")
    print(f"   Reward: ${risk_reward.reward_amount}")
    print(f"   Ratio: {risk_reward.risk_reward_ratio:.2f}")

    # Métriques de risque-récompense
    print(f"\n📈 Métriques de risque-récompense:")
    
    metrics = RiskRewardMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        average_risk_reward=2.5,
        max_risk_reward=4.0,
        min_risk_reward=1.2,
        median_risk_reward=2.3,
        total_risk=Decimal("2000"),
        total_reward=Decimal("5000"),
        success_rate=0.65,
        expected_value=Decimal("1250")
    )

    print(f"   Ratio moyen: {metrics.average_risk_reward:.2f}")
    print(f"   Ratio max: {metrics.max_risk_reward:.2f}")
    print(f"   Taux de succès: {metrics.success_rate*100:.1f}%")
    print(f"   Valeur attendue: ${metrics.expected_value}")

    # Critère de Kelly
    print(f"\n🎯 Critère de Kelly:")
    
    kelly = create_kelly_criterion(
        user_id=user_id,
        symbol="BTC/USDT",
        win_rate=0.65,
        average_win=Decimal("500"),
        average_loss=Decimal("250")
    )

    print(f"   Taux de victoire: {kelly.win_rate*100:.1f}%")
    print(f"   Fraction Kelly: {kelly.kelly_fraction:.2%}")
    print(f"   Fraction optimale: {kelly.optimal_fraction:.2%}")
    print(f"   Half Kelly: {kelly.half_kelly:.2%}")

    # Optimisation
    print(f"\n🎯 Optimisation de risque-récompense:")
    
    optimization = RiskRewardOptimization(
        optimization_id=uuid4(),
        user_id=user_id,
        symbol="BTC/USDT",
        optimal_stop_loss=Decimal("48500"),
        optimal_take_profit=Decimal("53000"),
        optimal_risk_reward=3.0,
        optimal_position_size=Decimal("0.12"),
        expected_return=Decimal("600"),
        sharpe_ratio=1.85,
        kelly_fraction=0.18
    )

    print(f"   Stop Loss optimal: ${optimization.optimal_stop_loss}")
    print(f"   Take Profit optimal: ${optimization.optimal_take_profit}")
    print(f"   Ratio optimal: {optimization.optimal_risk_reward:.2f}")
    print(f"   Sharpe Ratio: {optimization.sharpe_ratio:.2f}")

    print("\n" + "=" * 60)
    print("Risk-Reward Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
