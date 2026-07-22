"""
NEXUS AI TRADING SYSTEM - HEDGE BOT PRICING MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de pricing pour le Hedge Bot.
Définition des entités de prix, modèles, et métriques associées.

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

class PricingModelType(Enum):
    """Types de modèles de pricing."""
    BLACK_SCHOLES = "black_scholes"
    BINOMIAL = "binomial"
    MONTE_CARLO = "monte_carlo"
    FINITE_DIFFERENCE = "finite_difference"
    HESTON = "heston"
    SABR = "sabr"
    LOCAL_VOL = "local_vol"
    STOCHASTIC_VOL = "stochastic_vol"
    JUMP_DIFFUSION = "jump_diffusion"
    VIX = "vix"


class PricingStatus(Enum):
    """Statuts de pricing."""
    PENDING = "pending"
    CALCULATING = "calculating"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class PricingMethod(Enum):
    """Méthodes de pricing."""
    ANALYTICAL = "analytical"
    NUMERICAL = "numerical"
    SIMULATION = "simulation"
    HYBRID = "hybrid"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class PricingModelModel(Base):
    """Modèle de pricing."""
    __tablename__ = "pricing_models"

    model_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    model_type = Column(SQLEnum(PricingModelType), nullable=False)
    method = Column(SQLEnum(PricingMethod), nullable=False)
    status = Column(SQLEnum(PricingStatus), nullable=False)
    parameters = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    price = Column(Numeric(20, 8), nullable=True)
    implied_vol = Column(Float, nullable=True)
    delta = Column(Float, nullable=True)
    gamma = Column(Float, nullable=True)
    theta = Column(Float, nullable=True)
    vega = Column(Float, nullable=True)
    rho = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    iterations = Column(Integer, nullable=True)
    computation_time = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_pricing_models_user_id", "user_id"),
        Index("idx_pricing_models_symbol", "symbol"),
        Index("idx_pricing_models_type", "model_type"),
        Index("idx_pricing_models_status", "status"),
        Index("idx_pricing_models_calculated_at", "calculated_at"),
    )


class PricingDataModel(Base):
    """Modèle de données de pricing."""
    __tablename__ = "pricing_data"

    data_id = Column(String(36), primary_key=True)
    model_id = Column(String(36), ForeignKey("pricing_models.model_id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    spot_price = Column(Numeric(20, 8), nullable=False)
    strike_price = Column(Numeric(20, 8), nullable=False)
    time_to_expiry = Column(Float, nullable=False)
    risk_free_rate = Column(Float, nullable=False)
    volatility = Column(Float, nullable=False)
    dividend_yield = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

    # Relations
    model = relationship("PricingModelModel")

    __table_args__ = (
        Index("idx_pricing_data_model_id", "model_id"),
        Index("idx_pricing_data_user_id", "user_id"),
        Index("idx_pricing_data_symbol", "symbol"),
        Index("idx_pricing_data_timestamp", "timestamp"),
    )


class PricingSurfaceModel(Base):
    """Modèle de surface de pricing."""
    __tablename__ = "pricing_surfaces"

    surface_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    strikes = Column(JSON, nullable=False)
    expiries = Column(JSON, nullable=False)
    prices = Column(JSON, nullable=False)
    implied_vols = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_pricing_surfaces_user_id", "user_id"),
        Index("idx_pricing_surfaces_symbol", "symbol"),
        Index("idx_pricing_surfaces_generated_at", "generated_at"),
    )


class PricingMetricsModel(Base):
    """Modèle de métriques de pricing."""
    __tablename__ = "pricing_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    model_id = Column(String(36), ForeignKey("pricing_models.model_id"), nullable=False)
    total_models = Column(Integer, nullable=False)
    average_price = Column(Numeric(20, 8), nullable=False)
    max_price = Column(Numeric(20, 8), nullable=False)
    min_price = Column(Numeric(20, 8), nullable=False)
    average_vol = Column(Float, nullable=False)
    max_vol = Column(Float, nullable=False)
    min_vol = Column(Float, nullable=False)
    accuracy_score = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    model = relationship("PricingModelModel")

    __table_args__ = (
        Index("idx_pricing_metrics_user_id", "user_id"),
        Index("idx_pricing_metrics_model_id", "model_id"),
        Index("idx_pricing_metrics_calculated_at", "calculated_at"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class PricingModel:
    """Modèle de pricing."""
    model_id: UUID
    user_id: UUID
    symbol: str
    model_type: PricingModelType
    method: PricingMethod
    status: PricingStatus
    parameters: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    price: Optional[Decimal]
    implied_vol: Optional[float]
    delta: Optional[float]
    gamma: Optional[float]
    theta: Optional[float]
    vega: Optional[float]
    rho: Optional[float]
    accuracy: Optional[float]
    iterations: Optional[int]
    computation_time: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "model_id": str(self.model_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "model_type": self.model_type.value,
            "method": self.method.value,
            "status": self.status.value,
            "parameters": self.parameters,
            "result": self.result,
            "price": str(self.price) if self.price else None,
            "implied_vol": self.implied_vol,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "accuracy": self.accuracy,
            "iterations": self.iterations,
            "computation_time": self.computation_time,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class PricingData:
    """Données de pricing."""
    data_id: UUID
    model_id: UUID
    user_id: UUID
    symbol: str
    timestamp: datetime
    spot_price: Decimal
    strike_price: Decimal
    time_to_expiry: float
    risk_free_rate: float
    volatility: float
    dividend_yield: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "data_id": str(self.data_id),
            "model_id": str(self.model_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "spot_price": str(self.spot_price),
            "strike_price": str(self.strike_price),
            "time_to_expiry": self.time_to_expiry,
            "risk_free_rate": self.risk_free_rate,
            "volatility": self.volatility,
            "dividend_yield": self.dividend_yield,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class PricingSurface:
    """Surface de pricing."""
    surface_id: UUID
    user_id: UUID
    symbol: str
    strikes: List[float]
    expiries: List[float]
    prices: List[List[float]]
    implied_vols: List[List[float]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "surface_id": str(self.surface_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "strikes": self.strikes,
            "expiries": self.expiries,
            "prices": self.prices,
            "implied_vols": self.implied_vols,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class PricingMetrics:
    """Métriques de pricing."""
    metric_id: UUID
    user_id: UUID
    model_id: UUID
    total_models: int
    average_price: Decimal
    max_price: Decimal
    min_price: Decimal
    average_vol: float
    max_vol: float
    min_vol: float
    accuracy_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "model_id": str(self.model_id),
            "total_models": self.total_models,
            "average_price": str(self.average_price),
            "max_price": str(self.max_price),
            "min_price": str(self.min_price),
            "average_vol": self.average_vol,
            "max_vol": self.max_vol,
            "min_vol": self.min_vol,
            "accuracy_score": self.accuracy_score,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_pricing_model(
    user_id: UUID,
    symbol: str,
    model_type: PricingModelType,
    method: PricingMethod,
    parameters: Dict[str, Any],
    status: PricingStatus = PricingStatus.PENDING,
    metadata: Optional[Dict] = None
) -> PricingModel:
    """
    Crée un modèle de pricing.

    Args:
        user_id: ID de l'utilisateur
        symbol: Symbole
        model_type: Type de modèle
        method: Méthode
        parameters: Paramètres
        status: Statut
        metadata: Métadonnées

    Returns:
        Modèle de pricing
    """
    return PricingModel(
        model_id=uuid4(),
        user_id=user_id,
        symbol=symbol,
        model_type=model_type,
        method=method,
        status=status,
        parameters=parameters,
        result=None,
        price=None,
        implied_vol=None,
        delta=None,
        gamma=None,
        theta=None,
        vega=None,
        rho=None,
        accuracy=None,
        iterations=None,
        computation_time=None,
        metadata=metadata or {}
    )


def create_pricing_data(
    model_id: UUID,
    user_id: UUID,
    symbol: str,
    timestamp: datetime,
    spot_price: Decimal,
    strike_price: Decimal,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    dividend_yield: Optional[float] = None,
    metadata: Optional[Dict] = None
) -> PricingData:
    """
    Crée des données de pricing.

    Args:
        model_id: ID du modèle
        user_id: ID de l'utilisateur
        symbol: Symbole
        timestamp: Date/heure
        spot_price: Prix spot
        strike_price: Prix d'exercice
        time_to_expiry: Temps jusqu'à l'expiration
        risk_free_rate: Taux sans risque
        volatility: Volatilité
        dividend_yield: Rendement des dividendes
        metadata: Métadonnées

    Returns:
        Données de pricing
    """
    return PricingData(
        data_id=uuid4(),
        model_id=model_id,
        user_id=user_id,
        symbol=symbol,
        timestamp=timestamp,
        spot_price=spot_price,
        strike_price=strike_price,
        time_to_expiry=time_to_expiry,
        risk_free_rate=risk_free_rate,
        volatility=volatility,
        dividend_yield=dividend_yield,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PricingModelType",
    "PricingStatus",
    "PricingMethod",
    "PricingModelModel",
    "PricingDataModel",
    "PricingSurfaceModel",
    "PricingMetricsModel",
    "PricingModel",
    "PricingData",
    "PricingSurface",
    "PricingMetrics",
    "create_pricing_model",
    "create_pricing_data"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de pricing."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT PRICING MODELS")
    print("=" * 60)

    # Création d'un modèle de pricing
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Création d'un modèle de pricing...")
    
    model = create_pricing_model(
        user_id=user_id,
        symbol="BTC/USDT",
        model_type=PricingModelType.BLACK_SCHOLES,
        method=PricingMethod.ANALYTICAL,
        parameters={
            "volatility": 0.35,
            "risk_free_rate": 0.02,
            "time_to_expiry": 30
        },
        metadata={"source": "options_pricing"}
    )

    print(f"   ID: {model.model_id}")
    print(f"   Symbole: {model.symbol}")
    print(f"   Type: {model.model_type.value}")
    print(f"   Méthode: {model.method.value}")
    print(f"   Paramètres: {model.parameters}")

    # Création de données de pricing
    print(f"\n📈 Création de données de pricing...")
    
    data = create_pricing_data(
        model_id=model.model_id,
        user_id=user_id,
        symbol="BTC/USDT",
        timestamp=datetime.now(),
        spot_price=Decimal("50000"),
        strike_price=Decimal("52000"),
        time_to_expiry=30.0,
        risk_free_rate=0.02,
        volatility=0.35,
        dividend_yield=0.0
    )

    print(f"   ID: {data.data_id}")
    print(f"   Spot: ${data.spot_price}")
    print(f"   Strike: ${data.strike_price}")
    print(f"   Volatilité: {data.volatility:.1%}")
    print(f"   Temps: {data.time_to_expiry} jours")

    # Métriques
    print(f"\n📊 Métriques de pricing:")
    
    metrics = PricingMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        model_id=model.model_id,
        total_models=5,
        average_price=Decimal("2500"),
        max_price=Decimal("3500"),
        min_price=Decimal("1800"),
        average_vol=0.32,
        max_vol=0.38,
        min_vol=0.28,
        accuracy_score=0.92
    )

    print(f"   Prix moyen: ${metrics.average_price}")
    print(f"   Volatilité moyenne: {metrics.average_vol:.1%}")
    print(f"   Précision: {metrics.accuracy_score:.1%}")

    # Surface de pricing
    print(f"\n🌊 Surface de pricing...")
    
    surface = PricingSurface(
        surface_id=uuid4(),
        user_id=user_id,
        symbol="BTC/USDT",
        strikes=[48000, 50000, 52000, 54000, 56000],
        expiries=[7, 14, 30, 60, 90],
        prices=[
            [1200, 1500, 1800, 2100, 2400],
            [1800, 2200, 2600, 3000, 3400],
            [2500, 3000, 3500, 4000, 4500],
            [3200, 3800, 4400, 5000, 5600],
            [3800, 4500, 5200, 5900, 6600]
        ],
        implied_vols=[
            [0.32, 0.33, 0.35, 0.37, 0.39],
            [0.31, 0.32, 0.34, 0.36, 0.38],
            [0.30, 0.31, 0.33, 0.35, 0.37],
            [0.29, 0.30, 0.32, 0.34, 0.36],
            [0.28, 0.29, 0.31, 0.33, 0.35]
        ]
    )

    print(f"   Strikes: {surface.strikes}")
    print(f"   Expiries: {surface.expiries} jours")
    print(f"   Prix: {surface.prices[0]}")

    print("\n" + "=" * 60)
    print("Pricing Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
