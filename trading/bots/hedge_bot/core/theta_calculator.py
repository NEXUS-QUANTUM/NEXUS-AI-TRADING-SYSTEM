"""
NEXUS AI TRADING SYSTEM - HEDGE BOT THETA CALCULATOR MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de calcul du Theta pour le Hedge Bot.
Calcul du Theta, décroissance temporelle, et métriques associées.

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
from scipy import stats

from ..utils.helpers import (
    safe_decimal,
    safe_float,
    calculate_volatility,
    calculate_sharpe_ratio
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
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


@dataclass
class ThetaResult:
    """Résultat Theta."""
    theta_id: UUID
    option_id: UUID
    underlying_price: Decimal
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
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "theta_id": str(self.theta_id),
            "option_id": str(self.option_id),
            "underlying_price": str(self.underlying_price),
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
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ThetaMetrics:
    """Métriques Theta."""
    option_id: UUID
    theta_exposure: float
    theta_exposure_usd: Decimal
    theta_hedge_ratio: float
    time_decay_rate: float
    time_value_percent: float
    theta_risk: float
    theta_risk_category: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "option_id": str(self.option_id),
            "theta_exposure": self.theta_exposure,
            "theta_exposure_usd": str(self.theta_exposure_usd),
            "theta_hedge_ratio": self.theta_hedge_ratio,
            "time_decay_rate": self.time_decay_rate,
            "time_value_percent": self.time_value_percent,
            "theta_risk": self.theta_risk,
            "theta_risk_category": self.theta_risk_category,
            "metadata": self.metadata
        }


@dataclass
class TimeDecaySchedule:
    """Calendrier de décroissance temporelle."""
    schedule_id: UUID
    option_id: UUID
    dates: List[datetime]
    theta_values: List[float]
    time_values: List[float]
    intrinsic_values: List[float]
    decay_type: TimeDecayType
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "schedule_id": str(self.schedule_id),
            "option_id": str(self.option_id),
            "dates": [d.isoformat() for d in self.dates],
            "theta_values": self.theta_values,
            "time_values": self.time_values,
            "intrinsic_values": self.intrinsic_values,
            "decay_type": self.decay_type.value,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE THETA CALCULATOR
# ============================================================================

class ThetaCalculator:
    """
    Calculateur de Theta avancé.
    """

    # Constantes
    DAYS_PER_YEAR = 365.25

    # Seuils de risque Theta
    THETA_RISK_THRESHOLDS = {
        "low": 0.01,
        "medium": 0.05,
        "high": 0.10,
        "extreme": 0.20
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le calculateur de Theta.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._theta_cache: Dict[UUID, ThetaResult] = {}
        self._metrics_cache: Dict[UUID, ThetaMetrics] = {}
        self._schedule_cache: Dict[UUID, TimeDecaySchedule] = {}
        
        # Métriques
        self._metrics = {
            "total_calculations": 0,
            "by_type": {},
            "last_calculation": None
        }

        logger.info("ThetaCalculator initialisé avec succès")

    # ========================================================================
    # CALCUL DU THETA
    # ========================================================================

    async def calculate_theta(
        self,
        underlying_price: Decimal,
        strike_price: Decimal,
        time_to_expiry_days: int,
        risk_free_rate: float,
        volatility: float,
        option_type: str = "call",
        metadata: Optional[Dict] = None
    ) -> ThetaResult:
        """
        Calcule le Theta d'une option.

        Args:
            underlying_price: Prix du sous-jacent
            strike_price: Prix d'exercice
            time_to_expiry_days: Jours jusqu'à l'expiration
            risk_free_rate: Taux sans risque
            volatility: Volatilité
            option_type: Type d'option
            metadata: Métadonnées

        Returns:
            Résultat Theta
        """
        try:
            theta_id = uuid4()
            option_id = uuid4()
            self._metrics["total_calculations"] += 1
            self._metrics["last_calculation"] = datetime.now().isoformat()

            # Conversion
            S = float(underlying_price)
            K = float(strike_price)
            T = time_to_expiry_days / self.DAYS_PER_YEAR
            r = risk_free_rate
            sigma = volatility

            # Black-Scholes
            d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)

            # Theta (par jour)
            theta = -S * stats.norm.pdf(d1) * sigma / (2 * math.sqrt(T))
            theta -= r * K * math.exp(-r * T) * stats.norm.cdf(d2)
            if option_type == "put":
                theta += r * K * math.exp(-r * T)

            # Theta par jour
            theta_daily = theta / self.DAYS_PER_YEAR

            # Theta par semaine
            theta_weekly = theta_daily * 7

            # Décroissance temporelle
            theta_decay = theta_daily * T

            # Impact Theta (changement de prix pour 1 jour)
            theta_impact = theta_daily

            # Theta Ratio (theta / prix)
            if option_type == "call":
                option_price = S * stats.norm.cdf(d1) - K * math.exp(-r * T) * stats.norm.cdf(d2)
            else:
                option_price = K * math.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)

            theta_ratio = theta_daily / option_price if option_price > 0 else 0

            # Valeur intrinsèque et temps
            if option_type == "call":
                intrinsic_value = max(S - K, 0)
            else:
                intrinsic_value = max(K - S, 0)
            
            time_value = option_price - intrinsic_value

            result = ThetaResult(
                theta_id=theta_id,
                option_id=option_id,
                underlying_price=underlying_price,
                strike_price=strike_price,
                time_to_expiry=T,
                risk_free_rate=r,
                volatility=sigma,
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

            self._theta_cache[theta_id] = result

            type_key = option_type
            if type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][type_key] = 0
            self._metrics["by_type"][type_key] += 1

            return result

        except Exception as e:
            logger.error(f"Erreur de calcul du Theta: {e}")
            raise

    # ========================================================================
    # MÉTRIQUES THETA
    # ========================================================================

    async def get_theta_metrics(
        self,
        option_id: UUID,
        portfolio_value: Decimal,
        metadata: Optional[Dict] = None
    ) -> ThetaMetrics:
        """
        Calcule les métriques Theta.

        Args:
            option_id: ID de l'option
            portfolio_value: Valeur du portefeuille
            metadata: Métadonnées

        Returns:
            Métriques Theta
        """
        try:
            # Recherche du ThetaResult correspondant
            theta_result = None
            for result in self._theta_cache.values():
                if result.option_id == option_id:
                    theta_result = result
                    break

            if not theta_result:
                raise ValueError(f"Option {option_id} non trouvée")

            # Exposition Theta
            theta_exposure = abs(theta_result.theta_daily)
            theta_exposure_usd = Decimal(str(theta_exposure * float(portfolio_value)))

            # Ratio de hedge Theta
            theta_hedge_ratio = theta_exposure / float(portfolio_value) if float(portfolio_value) > 0 else 0

            # Taux de décroissance
            time_decay_rate = theta_exposure / theta_result.time_value if theta_result.time_value > 0 else 0

            # Pourcentage de valeur temps
            time_value_percent = (theta_result.time_value / (theta_result.time_value + theta_result.intrinsic_value) * 100) if (theta_result.time_value + theta_result.intrinsic_value) > 0 else 0

            # Risque Theta
            theta_risk = theta_exposure / float(portfolio_value) if float(portfolio_value) > 0 else 0

            # Catégorie de risque
            risk_category = self._get_risk_category(theta_risk)

            metrics = ThetaMetrics(
                option_id=option_id,
                theta_exposure=theta_exposure,
                theta_exposure_usd=theta_exposure_usd,
                theta_hedge_ratio=theta_hedge_ratio,
                time_decay_rate=time_decay_rate,
                time_value_percent=time_value_percent,
                theta_risk=theta_risk,
                theta_risk_category=risk_category,
                metadata=metadata or {}
            )

            self._metrics_cache[option_id] = metrics
            return metrics

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques Theta: {e}")
            raise

    def _get_risk_category(self, theta_risk: float) -> str:
        """
        Détermine la catégorie de risque Theta.

        Args:
            theta_risk: Risque Theta

        Returns:
            Catégorie de risque
        """
        if theta_risk < self.THETA_RISK_THRESHOLDS["low"]:
            return "low"
        elif theta_risk < self.THETA_RISK_THRESHOLDS["medium"]:
            return "medium"
        elif theta_risk < self.THETA_RISK_THRESHOLDS["high"]:
            return "high"
        else:
            return "extreme"

    # ========================================================================
    # CALENDRIER DE DÉCROISSANCE
    # ========================================================================

    async def generate_decay_schedule(
        self,
        option_id: UUID,
        days: int = 30,
        decay_type: TimeDecayType = TimeDecayType.EXPONENTIAL,
        metadata: Optional[Dict] = None
    ) -> TimeDecaySchedule:
        """
        Génère un calendrier de décroissance temporelle.

        Args:
            option_id: ID de l'option
            days: Nombre de jours
            decay_type: Type de décroissance
            metadata: Métadonnées

        Returns:
            Calendrier de décroissance
        """
        try:
            # Recherche du ThetaResult correspondant
            theta_result = None
            for result in self._theta_cache.values():
                if result.option_id == option_id:
                    theta_result = result
                    break

            if not theta_result:
                raise ValueError(f"Option {option_id} non trouvée")

            schedule_id = uuid4()
            now = datetime.now()

            dates = []
            theta_values = []
            time_values = []
            intrinsic_values = []

            S = float(theta_result.underlying_price)
            K = float(theta_result.strike_price)
            r = theta_result.risk_free_rate
            sigma = theta_result.volatility
            T = theta_result.time_to_expiry
            option_type = theta_result.option_type

            for i in range(days + 1):
                date = now + timedelta(days=i)
                dates.append(date)

                # Nouveau temps jusqu'à l'expiration
                new_T = max(T - i / self.DAYS_PER_YEAR, 0.001)

                # Calcul des nouveaux paramètres
                d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * new_T) / (sigma * math.sqrt(new_T))
                d2 = d1 - sigma * math.sqrt(new_T)

                # Prix de l'option
                if option_type == "call":
                    price = S * stats.norm.cdf(d1) - K * math.exp(-r * new_T) * stats.norm.cdf(d2)
                else:
                    price = K * math.exp(-r * new_T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)

                # Valeur intrinsèque
                if option_type == "call":
                    intrinsic = max(S - K, 0)
                else:
                    intrinsic = max(K - S, 0)

                time_value = price - intrinsic

                # Theta
                theta = -S * stats.norm.pdf(d1) * sigma / (2 * math.sqrt(new_T))
                theta -= r * K * math.exp(-r * new_T) * stats.norm.cdf(d2)
                if option_type == "put":
                    theta += r * K * math.exp(-r * new_T)

                theta_daily = theta / self.DAYS_PER_YEAR

                theta_values.append(theta_daily)
                time_values.append(time_value)
                intrinsic_values.append(intrinsic)

            schedule = TimeDecaySchedule(
                schedule_id=schedule_id,
                option_id=option_id,
                dates=dates,
                theta_values=theta_values,
                time_values=time_values,
                intrinsic_values=intrinsic_values,
                decay_type=decay_type,
                metadata=metadata or {}
            )

            self._schedule_cache[schedule_id] = schedule
            return schedule

        except Exception as e:
            logger.error(f"Erreur de génération du calendrier: {e}")
            raise

    # ========================================================================
    # ANALYSE DE DÉCROISSANCE
    # ========================================================================

    async def analyze_time_decay(
        self,
        option_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyse la décroissance temporelle.

        Args:
            option_id: ID de l'option
            days: Nombre de jours

        Returns:
            Analyse de décroissance
        """
        try:
            schedule = await self.generate_decay_schedule(option_id, days)

            # Calcul des métriques de décroissance
            total_decay = schedule.time_values[0] - schedule.time_values[-1]
            avg_decay = total_decay / days
            max_decay = max(schedule.theta_values)
            min_decay = min(schedule.theta_values)

            # Taux de décroissance
            decay_rate = (schedule.time_values[0] - schedule.time_values[-1]) / schedule.time_values[0] if schedule.time_values[0] > 0 else 0

            return {
                "option_id": str(option_id),
                "days": days,
                "total_decay": total_decay,
                "avg_decay": avg_decay,
                "max_decay": max_decay,
                "min_decay": min_decay,
                "decay_rate": decay_rate,
                "decay_type": schedule.decay_type.value,
                "schedule_id": str(schedule.schedule_id),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur d'analyse de décroissance: {e}")
            return {"error": str(e)}

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_theta_result(
        self,
        theta_id: UUID
    ) -> Optional[ThetaResult]:
        """
        Récupère un résultat Theta.

        Args:
            theta_id: ID du Theta

        Returns:
            Résultat Theta ou None
        """
        return self._theta_cache.get(theta_id)

    async def get_theta_metrics(
        self,
        option_id: UUID
    ) -> Optional[ThetaMetrics]:
        """
        Récupère les métriques Theta.

        Args:
            option_id: ID de l'option

        Returns:
            Métriques Theta ou None
        """
        return self._metrics_cache.get(option_id)

    async def get_decay_schedule(
        self,
        schedule_id: UUID
    ) -> Optional[TimeDecaySchedule]:
        """
        Récupère un calendrier de décroissance.

        Args:
            schedule_id: ID du calendrier

        Returns:
            Calendrier de décroissance ou None
        """
        return self._schedule_cache.get(schedule_id)

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_calculations": self._metrics["total_calculations"],
                "by_type": self._metrics["by_type"],
                "last_calculation": self._metrics["last_calculation"],
                "cached_theta": len(self._theta_cache),
                "cached_metrics": len(self._metrics_cache),
                "cached_schedules": len(self._schedule_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de ThetaCalculator...")
        self._theta_cache.clear()
        self._metrics_cache.clear()
        self._schedule_cache.clear()
        logger.info("ThetaCalculator fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_theta_calculator(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> ThetaCalculator:
    """
    Crée une instance de ThetaCalculator.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de ThetaCalculator
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return ThetaCalculator(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ThetaType",
    "TimeDecayType",
    "ThetaResult",
    "ThetaMetrics",
    "TimeDecaySchedule",
    "ThetaCalculator",
    "create_theta_calculator"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du ThetaCalculator."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT THETA CALCULATOR")
    print("=" * 60)

    # Création du calculateur
    calculator = create_theta_calculator()

    print(f"\n✅ ThetaCalculator initialisé")

    # Calcul du Theta
    print(f"\n📊 Calcul du Theta...")
    theta_result = await calculator.calculate_theta(
        underlying_price=Decimal("100"),
        strike_price=Decimal("105"),
        time_to_expiry_days=30,
        risk_free_rate=0.02,
        volatility=0.25,
        option_type="call"
    )

    print(f"   Theta: {theta_result.theta:.4f}")
    print(f"   Theta Daily: {theta_result.theta_daily:.4f}")
    print(f"   Theta Weekly: {theta_result.theta_weekly:.4f}")
    print(f"   Theta Decay: {theta_result.theta_decay:.4f}")
    print(f"   Theta Ratio: {theta_result.theta_ratio:.4f}")
    print(f"   Time Value: {theta_result.time_value:.4f}")
    print(f"   Intrinsic Value: {theta_result.intrinsic_value:.4f}")

    # Calcul du Theta pour un Put
    print(f"\n📊 Calcul du Theta pour un Put...")
    theta_put = await calculator.calculate_theta(
        underlying_price=Decimal("100"),
        strike_price=Decimal("95"),
        time_to_expiry_days=30,
        risk_free_rate=0.02,
        volatility=0.25,
        option_type="put"
    )

    print(f"   Theta Put: {theta_put.theta_daily:.4f}")

    # Métriques Theta
    print(f"\n📈 Métriques Theta...")
    portfolio_value = Decimal("100000")
    metrics = await calculator.get_theta_metrics(
        option_id=theta_result.option_id,
        portfolio_value=portfolio_value
    )

    print(f"   Exposition Theta: {metrics.theta_exposure:.4f}")
    print(f"   Exposition Theta USD: ${metrics.theta_exposure_usd}")
    print(f"   Ratio de hedge: {metrics.theta_hedge_ratio:.4f}")
    print(f"   Taux de décroissance: {metrics.time_decay_rate:.4f}")
    print(f"   Valeur temps: {metrics.time_value_percent:.1f}%")
    print(f"   Risque Theta: {metrics.theta_risk:.4f}")
    print(f"   Catégorie de risque: {metrics.theta_risk_category}")

    # Calendrier de décroissance
    print(f"\n📅 Calendrier de décroissance...")
    schedule = await calculator.generate_decay_schedule(
        option_id=theta_result.option_id,
        days=30,
        decay_type=TimeDecayType.EXPONENTIAL
    )

    print(f"   Jours: {len(schedule.dates)}")
    print(f"   Theta initial: {schedule.theta_values[0]:.4f}")
    print(f"   Theta final: {schedule.theta_values[-1]:.4f}")
    print(f"   Type de décroissance: {schedule.decay_type.value}")

    # Analyse de décroissance
    print(f"\n🔍 Analyse de décroissance...")
    analysis = await calculator.analyze_time_decay(
        option_id=theta_result.option_id,
        days=30
    )

    print(f"   Décroissance totale: {analysis.get('total_decay', 0):.4f}")
    print(f"   Décroissance moyenne: {analysis.get('avg_decay', 0):.4f}")
    print(f"   Taux de décroissance: {analysis.get('decay_rate', 0):.2%}")

    # Santé du service
    health = await calculator.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Calculs: {health['total_calculations']}")
    print(f"   Calendriers: {health['cached_schedules']}")

    # Fermeture
    await calculator.close()

    print("\n" + "=" * 60)
    print("ThetaCalculator NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
