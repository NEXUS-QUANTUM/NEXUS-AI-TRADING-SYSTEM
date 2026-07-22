"""
NEXUS AI TRADING SYSTEM - HEDGE BOT VEGA MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données Vega pour le Hedge Bot.
Définition des entités Vega, expositions, et métriques associées.

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

class VegaType(Enum):
    """Types de Vega."""
    VEGA = "vega"
    VEGA_IMPACT = "vega_impact"
    VEGA_RATIO = "vega_ratio"
    VOLGA = "volga"
    VANNA = "vanna"
    CHARM = "charm"
    VEGA_EXPOSURE = "vega_exposure"


class VegaRiskCategory(Enum):
    """Catégories de risque Vega."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class VegaHedgeStatus(Enum):
    """Statuts de hedge Vega."""
    PENDING = "pending"
    ACTIVE = "active"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class VegaResultModel(Base):
    """Modèle de résultat Vega."""
    __tablename__ = "vega_results"

    result_id = Column(String(36), primary_key=True)
    option_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    underlying_symbol = Column(String(50), nullable=False)
    strike_price = Column(Numeric(20, 8), nullable=False)
    time_to_expiry = Column(Float, nullable=False)
    risk_free_rate = Column(Float, nullable=False)
    volatility = Column(Float, nullable=False)
    option_type = Column(String(10), nullable=False)
    vega = Column(Float, nullable=False)
    vega_impact = Column(Float, nullable=False)
    vega_ratio = Column(Float, nullable=False)
    volga = Column(Float, nullable=False)
    vanna = Column(Float, nullable=False)
    charm = Column(Float, nullable=False)
    implied_volatility = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_vega_results_user_id", "user_id"),
        Index("idx_vega_results_option_id", "option_id"),
        Index("idx_vega_results_underlying", "underlying_symbol"),
        Index("idx_vega_results_calculated_at", "calculated_at"),
    )


class VegaExposureModel(Base):
    """Modèle d'exposition Vega."""
    __tablename__ = "vega_exposures"

    exposure_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    option_id = Column(String(36), nullable=False)
    portfolio_id = Column(String(36), nullable=True)
    vega_exposure = Column(Float, nullable=False)
    vega_exposure_usd = Column(Numeric(20, 8), nullable=False)
    vega_hedge_ratio = Column(Float, nullable=False)
    vega_sensitivity = Column(Float, nullable=False)
    volatility_rank = Column(Float, nullable=True)
    volatility_percentile = Column(Float, nullable=True)
    vega_risk = Column(Float, nullable=False)
    vega_risk_category = Column(SQLEnum(VegaRiskCategory), nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_vega_exposures_user_id", "user_id"),
        Index("idx_vega_exposures_option_id", "option_id"),
        Index("idx_vega_exposures_portfolio_id", "portfolio_id"),
        Index("idx_vega_exposures_calculated_at", "calculated_at"),
    )


class VegaHedgeModel(Base):
    """Modèle de hedge Vega."""
    __tablename__ = "vega_hedges"

    hedge_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    option_id = Column(String(36), nullable=False)
    underlying_symbol = Column(String(50), nullable=False)
    hedge_asset = Column(String(50), nullable=False)
    hedge_ratio = Column(Float, nullable=False)
    hedge_quantity = Column(Numeric(20, 8), nullable=False)
    hedge_cost = Column(Numeric(20, 8), nullable=False)
    hedge_vega = Column(Float, nullable=False)
    hedge_delta = Column(Float, nullable=False)
    status = Column(SQLEnum(VegaHedgeStatus), nullable=False)
    metadata = Column(JSON, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_vega_hedges_user_id", "user_id"),
        Index("idx_vega_hedges_option_id", "option_id"),
        Index("idx_vega_hedges_underlying", "underlying_symbol"),
        Index("idx_vega_hedges_status", "status"),
    )


class VolatilitySurfaceModel(Base):
    """Modèle de surface de volatilité."""
    __tablename__ = "volatility_surfaces"

    surface_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    surface_type = Column(String(50), nullable=False)  # constant, term_structure, smile, surface
    strikes = Column(JSON, nullable=False)
    expiries = Column(JSON, nullable=False)
    volatilities = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_volatility_surfaces_user_id", "user_id"),
        Index("idx_volatility_surfaces_symbol", "symbol"),
        Index("idx_volatility_surfaces_type", "surface_type"),
    )


class VegaMetricsModel(Base):
    """Modèle de métriques Vega."""
    __tablename__ = "vega_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    option_id = Column(String(36), nullable=False)
    portfolio_id = Column(String(36), nullable=True)
    total_vega_exposure = Column(Float, nullable=False)
    total_vega_exposure_usd = Column(Numeric(20, 8), nullable=False)
    average_vega = Column(Float, nullable=False)
    max_vega = Column(Float, nullable=False)
    min_vega = Column(Float, nullable=False)
    vega_concentration = Column(Float, nullable=False)
    vega_diversification = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_vega_metrics_user_id", "user_id"),
        Index("idx_vega_metrics_option_id", "option_id"),
        Index("idx_vega_metrics_portfolio_id", "portfolio_id"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class VegaResult:
    """Résultat Vega."""
    result_id: UUID
    option_id: UUID
    user_id: UUID
    underlying_symbol: str
    strike_price: Decimal
    time_to_expiry: float
    risk_free_rate: float
    volatility: float
    option_type: str
    vega: float
    vega_impact: float
    vega_ratio: float
    volga: float
    vanna: float
    charm: float
    implied_volatility: Optional[float] = None
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
            "vega": self.vega,
            "vega_impact": self.vega_impact,
            "vega_ratio": self.vega_ratio,
            "volga": self.volga,
            "vanna": self.vanna,
            "charm": self.charm,
            "implied_volatility": self.implied_volatility,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class VegaExposure:
    """Exposition Vega."""
    exposure_id: UUID
    user_id: UUID
    option_id: UUID
    portfolio_id: Optional[UUID]
    vega_exposure: float
    vega_exposure_usd: Decimal
    vega_hedge_ratio: float
    vega_sensitivity: float
    volatility_rank: Optional[float] = None
    volatility_percentile: Optional[float] = None
    vega_risk: float
    vega_risk_category: VegaRiskCategory
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
            "vega_exposure": self.vega_exposure,
            "vega_exposure_usd": str(self.vega_exposure_usd),
            "vega_hedge_ratio": self.vega_hedge_ratio,
            "vega_sensitivity": self.vega_sensitivity,
            "volatility_rank": self.volatility_rank,
            "volatility_percentile": self.volatility_percentile,
            "vega_risk": self.vega_risk,
            "vega_risk_category": self.vega_risk_category.value,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class VegaHedge:
    """Hedge Vega."""
    hedge_id: UUID
    user_id: UUID
    option_id: UUID
    underlying_symbol: str
    hedge_asset: str
    hedge_ratio: float
    hedge_quantity: Decimal
    hedge_cost: Decimal
    hedge_vega: float
    hedge_delta: float
    status: VegaHedgeStatus
    metadata: Dict[str, Any] = field(default_factory=dict)
    executed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "hedge_id": str(self.hedge_id),
            "user_id": str(self.user_id),
            "option_id": str(self.option_id),
            "underlying_symbol": self.underlying_symbol,
            "hedge_asset": self.hedge_asset,
            "hedge_ratio": self.hedge_ratio,
            "hedge_quantity": str(self.hedge_quantity),
            "hedge_cost": str(self.hedge_cost),
            "hedge_vega": self.hedge_vega,
            "hedge_delta": self.hedge_delta,
            "status": self.status.value,
            "metadata": self.metadata,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class VegaMetrics:
    """Métriques Vega."""
    metric_id: UUID
    user_id: UUID
    option_id: UUID
    portfolio_id: Optional[UUID]
    total_vega_exposure: float
    total_vega_exposure_usd: Decimal
    average_vega: float
    max_vega: float
    min_vega: float
    vega_concentration: float
    vega_diversification: float
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
            "total_vega_exposure": self.total_vega_exposure,
            "total_vega_exposure_usd": str(self.total_vega_exposure_usd),
            "average_vega": self.average_vega,
            "max_vega": self.max_vega,
            "min_vega": self.min_vega,
            "vega_concentration": self.vega_concentration,
            "vega_diversification": self.vega_diversification,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_vega_result(
    option_id: UUID,
    user_id: UUID,
    underlying_symbol: str,
    strike_price: Decimal,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    option_type: str,
    vega: float,
    vega_impact: float,
    vega_ratio: float,
    volga: float,
    vanna: float,
    charm: float,
    implied_volatility: Optional[float] = None,
    metadata: Optional[Dict] = None
) -> VegaResult:
    """
    Crée un résultat Vega.

    Args:
        option_id: ID de l'option
        user_id: ID de l'utilisateur
        underlying_symbol: Symbole du sous-jacent
        strike_price: Prix d'exercice
        time_to_expiry: Temps jusqu'à l'expiration
        risk_free_rate: Taux sans risque
        volatility: Volatilité
        option_type: Type d'option
        vega: Vega
        vega_impact: Impact Vega
        vega_ratio: Ratio Vega
        volga: Volga
        vanna: Vanna
        charm: Charm
        implied_volatility: Volatilité implicite
        metadata: Métadonnées

    Returns:
        Résultat Vega
    """
    return VegaResult(
        result_id=uuid4(),
        option_id=option_id,
        user_id=user_id,
        underlying_symbol=underlying_symbol,
        strike_price=strike_price,
        time_to_expiry=time_to_expiry,
        risk_free_rate=risk_free_rate,
        volatility=volatility,
        option_type=option_type,
        vega=vega,
        vega_impact=vega_impact,
        vega_ratio=vega_ratio,
        volga=volga,
        vanna=vanna,
        charm=charm,
        implied_volatility=implied_volatility,
        metadata=metadata or {}
    )


def create_vega_hedge(
    user_id: UUID,
    option_id: UUID,
    underlying_symbol: str,
    hedge_asset: str,
    hedge_ratio: float,
    hedge_quantity: Decimal,
    hedge_cost: Decimal,
    hedge_vega: float,
    hedge_delta: float,
    status: VegaHedgeStatus = VegaHedgeStatus.PENDING,
    metadata: Optional[Dict] = None
) -> VegaHedge:
    """
    Crée un hedge Vega.

    Args:
        user_id: ID de l'utilisateur
        option_id: ID de l'option
        underlying_symbol: Symbole du sous-jacent
        hedge_asset: Actif de hedge
        hedge_ratio: Ratio de hedge
        hedge_quantity: Quantité de hedge
        hedge_cost: Coût du hedge
        hedge_vega: Vega du hedge
        hedge_delta: Delta du hedge
        status: Statut du hedge
        metadata: Métadonnées

    Returns:
        Hedge Vega
    """
    return VegaHedge(
        hedge_id=uuid4(),
        user_id=user_id,
        option_id=option_id,
        underlying_symbol=underlying_symbol,
        hedge_asset=hedge_asset,
        hedge_ratio=hedge_ratio,
        hedge_quantity=hedge_quantity,
        hedge_cost=hedge_cost,
        hedge_vega=hedge_vega,
        hedge_delta=hedge_delta,
        status=status,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "VegaType",
    "VegaRiskCategory",
    "VegaHedgeStatus",
    "VegaResultModel",
    "VegaExposureModel",
    "VegaHedgeModel",
    "VolatilitySurfaceModel",
    "VegaMetricsModel",
    "VegaResult",
    "VegaExposure",
    "VegaHedge",
    "VegaMetrics",
    "create_vega_result",
    "create_vega_hedge"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles Vega."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT VEGA MODELS")
    print("=" * 60)

    # Création d'un résultat Vega
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    option_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'un résultat Vega...")
    
    result = create_vega_result(
        option_id=option_id,
        user_id=user_id,
        underlying_symbol="BTC/USDT",
        strike_price=Decimal("50000"),
        time_to_expiry=0.25,
        risk_free_rate=0.02,
        volatility=0.35,
        option_type="call",
        vega=0.45,
        vega_impact=0.0045,
        vega_ratio=0.12,
        volga=0.03,
        vanna=0.02,
        charm=-0.01,
        implied_volatility=0.32,
        metadata={"source": "black_scholes"}
    )

    print(f"   ID: {result.result_id}")
    print(f"   Vega: {result.vega:.4f}")
    print(f"   Vega Impact: {result.vega_impact:.4f}")
    print(f"   Volga: {result.volga:.4f}")
    print(f"   Vanna: {result.vanna:.4f}")
    print(f"   Charm: {result.charm:.4f}")

    # Création d'une exposition Vega
    print(f"\n📈 Création d'une exposition Vega...")
    
    exposure = VegaExposure(
        exposure_id=uuid4(),
        user_id=user_id,
        option_id=option_id,
        portfolio_id=None,
        vega_exposure=0.45,
        vega_exposure_usd=Decimal("45000"),
        vega_hedge_ratio=0.75,
        vega_sensitivity=0.008,
        volatility_rank=0.65,
        volatility_percentile=72.5,
        vega_risk=0.035,
        vega_risk_category=VegaRiskCategory.MEDIUM
    )

    print(f"   ID: {exposure.exposure_id}")
    print(f"   Exposition: {exposure.vega_exposure:.4f}")
    print(f"   Exposition USD: ${exposure.vega_exposure_usd}")
    print(f"   Risque: {exposure.vega_risk_category.value}")

    # Création d'un hedge Vega
    print(f"\n🔒 Création d'un hedge Vega...")
    
    hedge = create_vega_hedge(
        user_id=user_id,
        option_id=option_id,
        underlying_symbol="BTC/USDT",
        hedge_asset="ETH/USDT",
        hedge_ratio=0.8,
        hedge_quantity=Decimal("2.5"),
        hedge_cost=Decimal("3500"),
        hedge_vega=0.36,
        hedge_delta=0.65,
        status=VegaHedgeStatus.ACTIVE
    )

    print(f"   ID: {hedge.hedge_id}")
    print(f"   Actif de hedge: {hedge.hedge_asset}")
    print(f"   Ratio: {hedge.hedge_ratio:.2f}")
    print(f"   Coût: ${hedge.hedge_cost}")
    print(f"   Vega du hedge: {hedge.hedge_vega:.4f}")

    # Métriques Vega
    print(f"\n📊 Métriques Vega:")
    
    metrics = VegaMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        option_id=option_id,
        portfolio_id=None,
        total_vega_exposure=0.45,
        total_vega_exposure_usd=Decimal("45000"),
        average_vega=0.45,
        max_vega=0.45,
        min_vega=0.45,
        vega_concentration=1.0,
        vega_diversification=0.0
    )

    print(f"   Exposition totale: {metrics.total_vega_exposure:.4f}")
    print(f"   Concentration: {metrics.vega_concentration:.2%}")
    print(f"   Diversification: {metrics.vega_diversification:.2%}")

    print("\n" + "=" * 60)
    print("Vega Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
