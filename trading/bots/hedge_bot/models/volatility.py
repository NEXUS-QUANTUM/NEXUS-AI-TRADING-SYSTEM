"""
NEXUS AI TRADING SYSTEM - HEDGE BOT VOLATILITY MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de volatilité pour le Hedge Bot.
Définition des entités de volatilité, métriques, et prévisions.

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

class VolatilityType(Enum):
    """Types de volatilité."""
    HISTORICAL = "historical"
    IMPLIED = "implied"
    REALIZED = "realized"
    FORECAST = "forecast"
    GARCH = "garch"
    EWMA = "ewma"
    PARKINSON = "parkinson"
    GARMAN_KLASS = "garman_klass"
    ROGERS_SATCHELL = "rogers_satchell"
    YANG_ZHANG = "yang_zhang"


class VolatilityRegime(Enum):
    """Régimes de volatilité."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"
    CRISIS = "crisis"


class VolatilityPeriod(Enum):
    """Périodes de volatilité."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class CorrelationMethod(Enum):
    """Méthodes de corrélation."""
    PEARSON = "pearson"
    SPEARMAN = "spearman"
    KENDALL = "kendall"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class VolatilityMetricsModel(Base):
    """Modèle de métriques de volatilité."""
    __tablename__ = "volatility_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    volatility_type = Column(SQLEnum(VolatilityType), nullable=False)
    period = Column(SQLEnum(VolatilityPeriod), nullable=False)
    value = Column(Float, nullable=False)
    annualized = Column(Float, nullable=True)
    daily = Column(Float, nullable=True)
    weekly = Column(Float, nullable=True)
    monthly = Column(Float, nullable=True)
    regime = Column(SQLEnum(VolatilityRegime), nullable=True)
    percentile = Column(Float, nullable=True)
    z_score = Column(Float, nullable=True)
    sample_size = Column(Integer, nullable=True)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_volatility_metrics_user_id", "user_id"),
        Index("idx_volatility_metrics_symbol", "symbol"),
        Index("idx_volatility_metrics_type", "volatility_type"),
        Index("idx_volatility_metrics_period", "period"),
        Index("idx_volatility_metrics_calculated_at", "calculated_at"),
    )


class VolatilityForecastModel(Base):
    """Modèle de prévision de volatilité."""
    __tablename__ = "volatility_forecasts"

    forecast_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    method = Column(String(50), nullable=False)
    horizon = Column(Integer, nullable=False)
    values = Column(JSON, nullable=False)
    confidence_lower = Column(JSON, nullable=True)
    confidence_upper = Column(JSON, nullable=True)
    confidence_level = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_volatility_forecasts_user_id", "user_id"),
        Index("idx_volatility_forecasts_symbol", "symbol"),
        Index("idx_volatility_forecasts_method", "method"),
        Index("idx_volatility_forecasts_generated_at", "generated_at"),
    )


class VolatilitySurfaceModel(Base):
    """Modèle de surface de volatilité."""
    __tablename__ = "volatility_surfaces"

    surface_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    strikes = Column(JSON, nullable=False)
    expiries = Column(JSON, nullable=False)
    volatilities = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_volatility_surfaces_user_id", "user_id"),
        Index("idx_volatility_surfaces_symbol", "symbol"),
        Index("idx_volatility_surfaces_generated_at", "generated_at"),
    )


class CorrelationMatrixModel(Base):
    """Modèle de matrice de corrélation."""
    __tablename__ = "correlation_matrices"

    matrix_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    assets = Column(JSON, nullable=False)
    matrix = Column(JSON, nullable=False)
    p_values = Column(JSON, nullable=True)
    method = Column(SQLEnum(CorrelationMethod), nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_correlation_matrices_user_id", "user_id"),
        Index("idx_correlation_matrices_calculated_at", "calculated_at"),
    )


class VolatilityRegimeModel(Base):
    """Modèle de régime de volatilité."""
    __tablename__ = "volatility_regimes"

    regime_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    regime = Column(SQLEnum(VolatilityRegime), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    avg_volatility = Column(Float, nullable=False)
    min_volatility = Column(Float, nullable=False)
    max_volatility = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_volatility_regimes_user_id", "user_id"),
        Index("idx_volatility_regimes_symbol", "symbol"),
        Index("idx_volatility_regimes_regime", "regime"),
        Index("idx_volatility_regimes_start_date", "start_date"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class VolatilityMetrics:
    """Métriques de volatilité."""
    metric_id: UUID
    user_id: UUID
    symbol: str
    volatility_type: VolatilityType
    period: VolatilityPeriod
    value: float
    annualized: Optional[float] = None
    daily: Optional[float] = None
    weekly: Optional[float] = None
    monthly: Optional[float] = None
    regime: Optional[VolatilityRegime] = None
    percentile: Optional[float] = None
    z_score: Optional[float] = None
    sample_size: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "volatility_type": self.volatility_type.value,
            "period": self.period.value,
            "value": self.value,
            "annualized": self.annualized,
            "daily": self.daily,
            "weekly": self.weekly,
            "monthly": self.monthly,
            "regime": self.regime.value if self.regime else None,
            "percentile": self.percentile,
            "z_score": self.z_score,
            "sample_size": self.sample_size,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class VolatilityForecast:
    """Prévision de volatilité."""
    forecast_id: UUID
    user_id: UUID
    symbol: str
    method: str
    horizon: int
    values: List[float]
    confidence_lower: Optional[List[float]] = None
    confidence_upper: Optional[List[float]] = None
    confidence_level: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "forecast_id": str(self.forecast_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "method": self.method,
            "horizon": self.horizon,
            "values": self.values,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
            "confidence_level": self.confidence_level,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class VolatilitySurface:
    """Surface de volatilité."""
    surface_id: UUID
    user_id: UUID
    symbol: str
    strikes: List[float]
    expiries: List[int]
    volatilities: List[List[float]]
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
            "volatilities": self.volatilities,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class CorrelationMatrix:
    """Matrice de corrélation."""
    matrix_id: UUID
    user_id: UUID
    assets: List[str]
    matrix: List[List[float]]
    p_values: Optional[List[List[float]]] = None
    method: CorrelationMethod = CorrelationMethod.PEARSON
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "matrix_id": str(self.matrix_id),
            "user_id": str(self.user_id),
            "assets": self.assets,
            "matrix": self.matrix,
            "p_values": self.p_values,
            "method": self.method.value,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class VolatilityRegime:
    """Régime de volatilité."""
    regime_id: UUID
    user_id: UUID
    symbol: str
    regime: VolatilityRegime
    start_date: datetime
    end_date: Optional[datetime] = None
    avg_volatility: float
    min_volatility: float
    max_volatility: float
    duration_days: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "regime_id": str(self.regime_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "regime": self.regime.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "avg_volatility": self.avg_volatility,
            "min_volatility": self.min_volatility,
            "max_volatility": self.max_volatility,
            "duration_days": self.duration_days,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_volatility_metrics(
    user_id: UUID,
    symbol: str,
    volatility_type: VolatilityType,
    period: VolatilityPeriod,
    value: float,
    annualized: Optional[float] = None,
    daily: Optional[float] = None,
    weekly: Optional[float] = None,
    monthly: Optional[float] = None,
    regime: Optional[VolatilityRegime] = None,
    percentile: Optional[float] = None,
    z_score: Optional[float] = None,
    sample_size: Optional[int] = None,
    metadata: Optional[Dict] = None
) -> VolatilityMetrics:
    """
    Crée des métriques de volatilité.

    Args:
        user_id: ID de l'utilisateur
        symbol: Symbole
        volatility_type: Type de volatilité
        period: Période
        value: Valeur
        annualized: Valeur annualisée
        daily: Valeur quotidienne
        weekly: Valeur hebdomadaire
        monthly: Valeur mensuelle
        regime: Régime de volatilité
        percentile: Percentile
        z_score: Z-score
        sample_size: Taille de l'échantillon
        metadata: Métadonnées

    Returns:
        Métriques de volatilité
    """
    return VolatilityMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        symbol=symbol,
        volatility_type=volatility_type,
        period=period,
        value=value,
        annualized=annualized,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        regime=regime,
        percentile=percentile,
        z_score=z_score,
        sample_size=sample_size,
        metadata=metadata or {}
    )


def create_volatility_forecast(
    user_id: UUID,
    symbol: str,
    method: str,
    horizon: int,
    values: List[float],
    confidence_lower: Optional[List[float]] = None,
    confidence_upper: Optional[List[float]] = None,
    confidence_level: Optional[float] = None,
    metadata: Optional[Dict] = None,
    expires_at: Optional[datetime] = None
) -> VolatilityForecast:
    """
    Crée une prévision de volatilité.

    Args:
        user_id: ID de l'utilisateur
        symbol: Symbole
        method: Méthode
        horizon: Horizon
        values: Valeurs prévues
        confidence_lower: Intervalle inférieur
        confidence_upper: Intervalle supérieur
        confidence_level: Niveau de confiance
        metadata: Métadonnées
        expires_at: Date d'expiration

    Returns:
        Prévision de volatilité
    """
    return VolatilityForecast(
        forecast_id=uuid4(),
        user_id=user_id,
        symbol=symbol,
        method=method,
        horizon=horizon,
        values=values,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        confidence_level=confidence_level,
        metadata=metadata or {},
        expires_at=expires_at
    )


def create_correlation_matrix(
    user_id: UUID,
    assets: List[str],
    matrix: List[List[float]],
    method: CorrelationMethod = CorrelationMethod.PEARSON,
    p_values: Optional[List[List[float]]] = None,
    metadata: Optional[Dict] = None
) -> CorrelationMatrix:
    """
    Crée une matrice de corrélation.

    Args:
        user_id: ID de l'utilisateur
        assets: Liste des actifs
        matrix: Matrice de corrélation
        method: Méthode
        p_values: P-values
        metadata: Métadonnées

    Returns:
        Matrice de corrélation
    """
    return CorrelationMatrix(
        matrix_id=uuid4(),
        user_id=user_id,
        assets=assets,
        matrix=matrix,
        p_values=p_values,
        method=method,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "VolatilityType",
    "VolatilityRegime",
    "VolatilityPeriod",
    "CorrelationMethod",
    "VolatilityMetricsModel",
    "VolatilityForecastModel",
    "VolatilitySurfaceModel",
    "CorrelationMatrixModel",
    "VolatilityRegimeModel",
    "VolatilityMetrics",
    "VolatilityForecast",
    "VolatilitySurface",
    "CorrelationMatrix",
    "VolatilityRegime",
    "create_volatility_metrics",
    "create_volatility_forecast",
    "create_correlation_matrix"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de volatilité."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT VOLATILITY MODELS")
    print("=" * 60)

    # Création de métriques de volatilité
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Création de métriques de volatilité...")
    
    metrics = create_volatility_metrics(
        user_id=user_id,
        symbol="BTC/USDT",
        volatility_type=VolatilityType.HISTORICAL,
        period=VolatilityPeriod.DAILY,
        value=0.02,
        annualized=0.32,
        daily=0.02,
        weekly=0.045,
        monthly=0.09,
        regime=VolatilityRegime.NORMAL,
        percentile=65.5,
        z_score=0.8,
        sample_size=252
    )

    print(f"   ID: {metrics.metric_id}")
    print(f"   Symbole: {metrics.symbol}")
    print(f"   Volatilité: {metrics.value*100:.2f}%")
    print(f"   Annualisée: {metrics.annualized*100:.2f}%")
    print(f"   Régime: {metrics.regime.value}")
    print(f"   Percentile: {metrics.percentile:.1f}%")

    # Création d'une prévision
    print(f"\n🔮 Création d'une prévision de volatilité...")
    
    values = [0.02, 0.022, 0.025, 0.028, 0.03]
    lower = [0.015, 0.017, 0.019, 0.021, 0.023]
    upper = [0.025, 0.027, 0.031, 0.035, 0.037]

    forecast = create_volatility_forecast(
        user_id=user_id,
        symbol="BTC/USDT",
        method="garch",
        horizon=5,
        values=values,
        confidence_lower=lower,
        confidence_upper=upper,
        confidence_level=0.95
    )

    print(f"   ID: {forecast.forecast_id}")
    print(f"   Méthode: {forecast.method}")
    print(f"   Horizon: {forecast.horizon} jours")
    print(f"   Valeurs: {forecast.values}")

    # Création d'une matrice de corrélation
    print(f"\n📈 Création d'une matrice de corrélation...")
    
    assets = ["BTC", "ETH", "SOL", "USDC"]
    matrix = [
        [1.0, 0.8, 0.6, 0.1],
        [0.8, 1.0, 0.7, 0.1],
        [0.6, 0.7, 1.0, 0.2],
        [0.1, 0.1, 0.2, 1.0]
    ]

    corr_matrix = create_correlation_matrix(
        user_id=user_id,
        assets=assets,
        matrix=matrix,
        method=CorrelationMethod.PEARSON
    )

    print(f"   ID: {corr_matrix.matrix_id}")
    print(f"   Actifs: {corr_matrix.assets}")
    print(f"   Matrice: {corr_matrix.matrix[0]}")

    # Création d'un régime de volatilité
    print(f"\n📋 Création d'un régime de volatilité...")
    
    regime = VolatilityRegime(
        regime_id=uuid4(),
        user_id=user_id,
        symbol="BTC/USDT",
        regime=VolatilityRegime.HIGH,
        start_date=datetime.now() - timedelta(days=30),
        avg_volatility=0.045,
        min_volatility=0.035,
        max_volatility=0.065,
        duration_days=30
    )

    print(f"   ID: {regime.regime_id}")
    print(f"   Régime: {regime.regime.value}")
    print(f"   Durée: {regime.duration_days} jours")
    print(f"   Volatilité moyenne: {regime.avg_volatility*100:.2f}%")

    print("\n" + "=" * 60)
    print("Volatility Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
