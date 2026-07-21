"""
NEXUS AI TRADING SYSTEM - HEDGE BOT VEGA CALCULATOR MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de calcul du Vega pour le Hedge Bot.
Calcul du Vega, sensibilité à la volatilité, et métriques associées.

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
from scipy.optimize import brentq

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

class VegaType(Enum):
    """Types de Vega."""
    VEGA = "vega"
    VEGA_IMPACT = "vega_impact"
    VEGA_RATIO = "vega_ratio"
    VOLGA = "volga"  # Vanna-Volga
    VANNA = "vanna"
    CHARM = "charm"


class VolatilitySurfaceType(Enum):
    """Types de surface de volatilité."""
    CONSTANT = "constant"
    TERM_STRUCTURE = "term_structure"
    SMILE = "smile"
    SURFACE = "surface"


@dataclass
class VegaResult:
    """Résultat Vega."""
    vega_id: UUID
    option_id: UUID
    underlying_price: Decimal
    strike_price: Decimal
    time_to_expiry: float
    risk_free_rate: float
    volatility: float
    option_type: str  # call, put
    vega: float
    vega_impact: float
    vega_ratio: float
    volga: float
    vanna: float
    charm: float
    implied_volatility: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "vega_id": str(self.vega_id),
            "option_id": str(self.option_id),
            "underlying_price": str(self.underlying_price),
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
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class VegaMetrics:
    """Métriques Vega."""
    option_id: UUID
    vega_exposure: float
    vega_exposure_usd: Decimal
    vega_hedge_ratio: float
    vega_sensitivity: float
    volatility_rank: float
    volatility_percentile: float
    vega_risk: float
    vega_risk_category: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "option_id": str(self.option_id),
            "vega_exposure": self.vega_exposure,
            "vega_exposure_usd": str(self.vega_exposure_usd),
            "vega_hedge_ratio": self.vega_hedge_ratio,
            "vega_sensitivity": self.vega_sensitivity,
            "volatility_rank": self.volatility_rank,
            "volatility_percentile": self.volatility_percentile,
            "vega_risk": self.vega_risk,
            "vega_risk_category": self.vega_risk_category,
            "metadata": self.metadata
        }


@dataclass
class VegaHedge:
    """Hedge Vega."""
    hedge_id: UUID
    option_id: UUID
    underlying: str
    hedge_asset: str
    hedge_ratio: float
    hedge_quantity: Decimal
    hedge_cost: Decimal
    hedge_vega: float
    hedge_delta: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "hedge_id": str(self.hedge_id),
            "option_id": str(self.option_id),
            "underlying": self.underlying,
            "hedge_asset": self.hedge_asset,
            "hedge_ratio": self.hedge_ratio,
            "hedge_quantity": str(self.hedge_quantity),
            "hedge_cost": str(self.hedge_cost),
            "hedge_vega": self.hedge_vega,
            "hedge_delta": self.hedge_delta,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


# ============================================================================
# CLASSE VEGA CALCULATOR
# ============================================================================

class VegaCalculator:
    """
    Calculateur de Vega avancé.
    """

    # Constantes
    DAYS_PER_YEAR = 365.25

    # Seuils de risque Vega
    VEGA_RISK_THRESHOLDS = {
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
        Initialise le calculateur de Vega.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._vega_cache: Dict[UUID, VegaResult] = {}
        self._metrics_cache: Dict[UUID, VegaMetrics] = {}
        self._hedge_cache: Dict[UUID, VegaHedge] = {}
        self._volatility_surface: Dict[str, Dict[str, float]] = {}
        
        # Métriques
        self._metrics = {
            "total_calculations": 0,
            "total_hedges": 0,
            "by_type": {},
            "last_calculation": None
        }

        logger.info("VegaCalculator initialisé avec succès")

    # ========================================================================
    # CALCUL DU VEGA
    # ========================================================================

    async def calculate_vega(
        self,
        underlying_price: Decimal,
        strike_price: Decimal,
        time_to_expiry_days: int,
        risk_free_rate: float,
        volatility: float,
        option_type: str = "call",
        metadata: Optional[Dict] = None
    ) -> VegaResult:
        """
        Calcule le Vega d'une option.

        Args:
            underlying_price: Prix du sous-jacent
            strike_price: Prix d'exercice
            time_to_expiry_days: Jours jusqu'à l'expiration
            risk_free_rate: Taux sans risque
            volatility: Volatilité
            option_type: Type d'option
            metadata: Métadonnées

        Returns:
            Résultat Vega
        """
        try:
            vega_id = uuid4()
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

            # Vega
            vega = S * stats.norm.pdf(d1) * math.sqrt(T)

            # Vega Impact (changement de prix pour 1% de vol)
            vega_impact = vega * 0.01

            # Vega Ratio (vega / prix)
            if option_type == "call":
                option_price = S * stats.norm.cdf(d1) - K * math.exp(-r * T) * stats.norm.cdf(d2)
            else:
                option_price = K * math.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)

            vega_ratio = vega / option_price if option_price > 0 else 0

            # Volga (Vega convexité)
            volga = vega * d1 * d2 / sigma

            # Vanna (cross gamma)
            vanna = -vega * d2 / sigma

            # Charm (delta decay)
            charm = -stats.norm.pdf(d1) * (2 * r * T - d2 * sigma * math.sqrt(T)) / (2 * T * sigma * math.sqrt(T))

            # Volatilité implicite (simulée)
            implied_vol = sigma * (1 + 0.1 * np.random.random())

            result = VegaResult(
                vega_id=vega_id,
                option_id=option_id,
                underlying_price=underlying_price,
                strike_price=strike_price,
                time_to_expiry=T,
                risk_free_rate=r,
                volatility=sigma,
                option_type=option_type,
                vega=vega,
                vega_impact=vega_impact,
                vega_ratio=vega_ratio,
                volga=volga,
                vanna=vanna,
                charm=charm,
                implied_volatility=implied_vol,
                metadata=metadata or {}
            )

            self._vega_cache[vega_id] = result

            type_key = option_type
            if type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][type_key] = 0
            self._metrics["by_type"][type_key] += 1

            return result

        except Exception as e:
            logger.error(f"Erreur de calcul du Vega: {e}")
            raise

    # ========================================================================
    # MÉTRIQUES VEGA
    # ========================================================================

    async def get_vega_metrics(
        self,
        option_id: UUID,
        portfolio_value: Decimal,
        metadata: Optional[Dict] = None
    ) -> VegaMetrics:
        """
        Calcule les métriques Vega.

        Args:
            option_id: ID de l'option
            portfolio_value: Valeur du portefeuille
            metadata: Métadonnées

        Returns:
            Métriques Vega
        """
        try:
            # Recherche du VegaResult correspondant
            vega_result = None
            for result in self._vega_cache.values():
                if result.option_id == option_id:
                    vega_result = result
                    break

            if not vega_result:
                raise ValueError(f"Option {option_id} non trouvée")

            # Exposition Vega
            vega_exposure = vega_result.vega
            vega_exposure_usd = Decimal(str(vega_exposure * float(portfolio_value)))

            # Ratio de hedge Vega
            vega_hedge_ratio = vega_exposure / float(portfolio_value) if float(portfolio_value) > 0 else 0

            # Sensibilité Vega
            vega_sensitivity = vega_exposure * vega_result.vega_impact

            # Rank de volatilité
            vol_rank = await self._get_volatility_rank(vega_result.option_id)

            # Percentile de volatilité
            vol_percentile = await self._get_volatility_percentile(vega_result.option_id)

            # Risque Vega
            vega_risk = abs(vega_exposure) / float(portfolio_value) if float(portfolio_value) > 0 else 0

            # Catégorie de risque
            risk_category = self._get_risk_category(vega_risk)

            metrics = VegaMetrics(
                option_id=option_id,
                vega_exposure=vega_exposure,
                vega_exposure_usd=vega_exposure_usd,
                vega_hedge_ratio=vega_hedge_ratio,
                vega_sensitivity=vega_sensitivity,
                volatility_rank=vol_rank,
                volatility_percentile=vol_percentile,
                vega_risk=vega_risk,
                vega_risk_category=risk_category,
                metadata=metadata or {}
            )

            self._metrics_cache[option_id] = metrics
            return metrics

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques Vega: {e}")
            raise

    def _get_risk_category(self, vega_risk: float) -> str:
        """
        Détermine la catégorie de risque Vega.

        Args:
            vega_risk: Risque Vega

        Returns:
            Catégorie de risque
        """
        if vega_risk < self.VEGA_RISK_THRESHOLDS["low"]:
            return "low"
        elif vega_risk < self.VEGA_RISK_THRESHOLDS["medium"]:
            return "medium"
        elif vega_risk < self.VEGA_RISK_THRESHOLDS["high"]:
            return "high"
        else:
            return "extreme"

    # ========================================================================
    # HEDGE VEGA
    # ========================================================================

    async def hedge_vega(
        self,
        option_id: UUID,
        underlying: str,
        hedge_asset: str,
        target_vega: float = 0,
        metadata: Optional[Dict] = None
    ) -> VegaHedge:
        """
        Génère un hedge Vega.

        Args:
            option_id: ID de l'option
            underlying: Sous-jacent
            hedge_asset: Actif de hedge
            target_vega: Vega cible
            metadata: Métadonnées

        Returns:
            Hedge Vega
        """
        try:
            # Récupération du VegaResult
            vega_result = None
            for result in self._vega_cache.values():
                if result.option_id == option_id:
                    vega_result = result
                    break

            if not vega_result:
                raise ValueError(f"Option {option_id} non trouvée")

            # Calcul du ratio de hedge
            hedge_vega = await self._get_asset_vega(hedge_asset)
            hedge_ratio = (vega_result.vega - target_vega) / hedge_vega if hedge_vega != 0 else 0

            # Quantité de hedge
            hedge_quantity = Decimal(str(abs(hedge_ratio)))

            # Coût du hedge
            hedge_cost = await self._get_asset_price(hedge_asset) * hedge_quantity

            # Delta du hedge
            hedge_delta = await self._get_asset_delta(hedge_asset) * hedge_ratio

            hedge = VegaHedge(
                hedge_id=uuid4(),
                option_id=option_id,
                underlying=underlying,
                hedge_asset=hedge_asset,
                hedge_ratio=hedge_ratio,
                hedge_quantity=hedge_quantity,
                hedge_cost=hedge_cost,
                hedge_vega=hedge_vega,
                hedge_delta=hedge_delta,
                metadata=metadata or {}
            )

            self._hedge_cache[hedge.hedge_id] = hedge
            self._metrics["total_hedges"] += 1

            return hedge

        except Exception as e:
            logger.error(f"Erreur de génération du hedge Vega: {e}")
            raise

    # ========================================================================
    # SURFACE DE VOLATILITÉ
    # ========================================================================

    async def build_volatility_surface(
        self,
        symbol: str,
        strikes: List[float],
        expiries: List[int],
        volatilities: List[List[float]],
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Construit une surface de volatilité.

        Args:
            symbol: Symbole
            strikes: Prix d'exercice
            expiries: Jours jusqu'à l'expiration
            volatilities: Volatilités (matrice)
            metadata: Métadonnées

        Returns:
            Surface de volatilité
        """
        try:
            surface = {
                "symbol": symbol,
                "strikes": strikes,
                "expiries": expiries,
                "volatilities": volatilities,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            self._volatility_surface[symbol] = surface
            return surface

        except Exception as e:
            logger.error(f"Erreur de construction de la surface: {e}")
            return {}

    async def get_volatility_surface(
        self,
        symbol: str
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère une surface de volatilité.

        Args:
            symbol: Symbole

        Returns:
            Surface de volatilité
        """
        return self._volatility_surface.get(symbol)

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def _get_volatility_rank(self, option_id: UUID) -> float:
        """
        Récupère le rank de volatilité.

        Args:
            option_id: ID de l'option

        Returns:
            Rank de volatilité
        """
        # Simulation
        return 0.5 + 0.3 * np.random.random()

    async def _get_volatility_percentile(self, option_id: UUID) -> float:
        """
        Récupère le percentile de volatilité.

        Args:
            option_id: ID de l'option

        Returns:
            Percentile de volatilité
        """
        return np.random.random() * 100

    async def _get_asset_vega(self, asset: str) -> float:
        """
        Récupère le Vega d'un actif.

        Args:
            asset: Actif

        Returns:
            Vega
        """
        # Simulation
        return 0.1 + 0.05 * np.random.random()

    async def _get_asset_price(self, asset: str) -> Decimal:
        """
        Récupère le prix d'un actif.

        Args:
            asset: Actif

        Returns:
            Prix
        """
        # Simulation
        return Decimal(str(100 + 50 * np.random.random()))

    async def _get_asset_delta(self, asset: str) -> float:
        """
        Récupère le Delta d'un actif.

        Args:
            asset: Actif

        Returns:
            Delta
        """
        # Simulation
        return 0.5 + 0.4 * np.random.random()

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_vega_result(
        self,
        vega_id: UUID
    ) -> Optional[VegaResult]:
        """
        Récupère un résultat Vega.

        Args:
            vega_id: ID du Vega

        Returns:
            Résultat Vega ou None
        """
        return self._vega_cache.get(vega_id)

    async def get_vega_metrics(
        self,
        option_id: UUID
    ) -> Optional[VegaMetrics]:
        """
        Récupère les métriques Vega.

        Args:
            option_id: ID de l'option

        Returns:
            Métriques Vega ou None
        """
        return self._metrics_cache.get(option_id)

    async def get_hedge(
        self,
        hedge_id: UUID
    ) -> Optional[VegaHedge]:
        """
        Récupère un hedge Vega.

        Args:
            hedge_id: ID du hedge

        Returns:
            Hedge Vega ou None
        """
        return self._hedge_cache.get(hedge_id)

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
                "total_hedges": self._metrics["total_hedges"],
                "by_type": self._metrics["by_type"],
                "last_calculation": self._metrics["last_calculation"],
                "cached_vega": len(self._vega_cache),
                "cached_metrics": len(self._metrics_cache),
                "cached_hedges": len(self._hedge_cache),
                "volatility_surfaces": len(self._volatility_surface),
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
        logger.info("Fermeture de VegaCalculator...")
        self._vega_cache.clear()
        self._metrics_cache.clear()
        self._hedge_cache.clear()
        self._volatility_surface.clear()
        logger.info("VegaCalculator fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_vega_calculator(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> VegaCalculator:
    """
    Crée une instance de VegaCalculator.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de VegaCalculator
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return VegaCalculator(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "VegaType",
    "VolatilitySurfaceType",
    "VegaResult",
    "VegaMetrics",
    "VegaHedge",
    "VegaCalculator",
    "create_vega_calculator"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du VegaCalculator."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT VEGA CALCULATOR")
    print("=" * 60)

    # Création du calculateur
    calculator = create_vega_calculator()

    print(f"\n✅ VegaCalculator initialisé")

    # Calcul du Vega
    print(f"\n📊 Calcul du Vega...")
    vega_result = await calculator.calculate_vega(
        underlying_price=Decimal("100"),
        strike_price=Decimal("105"),
        time_to_expiry_days=30,
        risk_free_rate=0.02,
        volatility=0.25,
        option_type="call"
    )

    print(f"   Vega: {vega_result.vega:.4f}")
    print(f"   Vega Impact: {vega_result.vega_impact:.4f}")
    print(f"   Vega Ratio: {vega_result.vega_ratio:.4f}")
    print(f"   Volga: {vega_result.volga:.4f}")
    print(f"   Vanna: {vega_result.vanna:.4f}")
    print(f"   Charm: {vega_result.charm:.4f}")

    # Calcul des métriques Vega
    print(f"\n📈 Métriques Vega...")
    portfolio_value = Decimal("100000")
    metrics = await calculator.get_vega_metrics(
        option_id=vega_result.option_id,
        portfolio_value=portfolio_value
    )

    print(f"   Exposition Vega: {metrics.vega_exposure:.4f}")
    print(f"   Exposition Vega USD: ${metrics.vega_exposure_usd}")
    print(f"   Ratio de hedge: {metrics.vega_hedge_ratio:.4f}")
    print(f"   Risque Vega: {metrics.vega_risk:.4f}")
    print(f"   Catégorie de risque: {metrics.vega_risk_category}")

    # Hedge Vega
    print(f"\n🔒 Hedge Vega...")
    hedge = await calculator.hedge_vega(
        option_id=vega_result.option_id,
        underlying="BTC",
        hedge_asset="ETH",
        target_vega=0
    )

    print(f"   Actif de hedge: {hedge.hedge_asset}")
    print(f"   Ratio de hedge: {hedge.hedge_ratio:.4f}")
    print(f"   Quantité: {hedge.hedge_quantity}")
    print(f"   Coût: ${hedge.hedge_cost}")
    print(f"   Vega du hedge: {hedge.hedge_vega:.4f}")

    # Surface de volatilité
    print(f"\n🌊 Surface de volatilité...")
    strikes = [90, 95, 100, 105, 110]
    expiries = [7, 14, 30, 60]
    volatilities = [
        [0.20, 0.22, 0.25, 0.28, 0.30],
        [0.22, 0.24, 0.27, 0.30, 0.32],
        [0.25, 0.27, 0.30, 0.33, 0.35],
        [0.28, 0.30, 0.33, 0.36, 0.38]
    ]

    surface = await calculator.build_volatility_surface(
        symbol="BTC",
        strikes=strikes,
        expiries=expiries,
        volatilities=volatilities
    )

    print(f"   Symbole: {surface['symbol']}")
    print(f"   Strikes: {surface['strikes']}")
    print(f"   Expiries: {surface['expiries']}")

    # Santé du service
    health = await calculator.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Calculs: {health['total_calculations']}")
    print(f"   Hedges: {health['total_hedges']}")
    print(f"   Surfaces de volatilité: {health['volatility_surfaces']}")

    # Fermeture
    await calculator.close()

    print("\n" + "=" * 60)
    print("VegaCalculator NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
