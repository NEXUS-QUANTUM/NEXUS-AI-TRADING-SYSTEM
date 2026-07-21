"""
NEXUS AI TRADING SYSTEM - HEDGE BOT DELTA CALCULATOR MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de calcul du Delta pour le Hedge Bot.
Calcul du Delta, Gamma, Theta, Vega, et métriques d'options.

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

class OptionType(Enum):
    """Types d'options."""
    CALL = "call"
    PUT = "put"


class OptionStyle(Enum):
    """Styles d'options."""
    EUROPEAN = "european"
    AMERICAN = "american"
    BERMUDAN = "bermudan"
    EXOTIC = "exotic"


class GreeksType(Enum):
    """Types de Greeks."""
    DELTA = "delta"
    GAMMA = "gamma"
    THETA = "theta"
    VEGA = "vega"
    RHO = "rho"
    ALL = "all"


@dataclass
class GreeksResult:
    """Résultat des Greeks."""
    option_id: UUID
    underlying_price: Decimal
    strike_price: Decimal
    time_to_expiry: float  # années
    risk_free_rate: float
    volatility: float
    option_type: OptionType
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: float
    option_price: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "option_id": str(self.option_id),
            "underlying_price": str(self.underlying_price),
            "strike_price": str(self.strike_price),
            "time_to_expiry": self.time_to_expiry,
            "risk_free_rate": self.risk_free_rate,
            "volatility": self.volatility,
            "option_type": self.option_type.value,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "implied_volatility": self.implied_volatility,
            "option_price": self.option_price,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class OptionMetrics:
    """Métriques d'options."""
    option_id: UUID
    intrinsic_value: Decimal
    time_value: Decimal
    moneyness: float
    probability_itm: float
    probability_otm: float
    expected_value: Decimal
    expected_payoff: Decimal
    implied_volatility_rank: float
    historical_volatility: float
    volatility_spread: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "option_id": str(self.option_id),
            "intrinsic_value": str(self.intrinsic_value),
            "time_value": str(self.time_value),
            "moneyness": self.moneyness,
            "probability_itm": self.probability_itm,
            "probability_otm": self.probability_otm,
            "expected_value": str(self.expected_value),
            "expected_payoff": str(self.expected_payoff),
            "implied_volatility_rank": self.implied_volatility_rank,
            "historical_volatility": self.historical_volatility,
            "volatility_spread": self.volatility_spread,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE DELTA CALCULATOR
# ============================================================================

class DeltaCalculator:
    """
    Calculateur de Delta et Greeks avancé.
    """

    # Constantes
    DAYS_PER_YEAR = 365.25

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le calculateur de Delta.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._greeks_cache: Dict[UUID, GreeksResult] = {}
        self._metrics_cache: Dict[UUID, OptionMetrics] = {}
        self._volatility_cache: Dict[str, float] = {}
        
        # Métriques
        self._metrics = {
            "total_calculations": 0,
            "by_type": {},
            "last_calculation": None
        }

        logger.info("DeltaCalculator initialisé avec succès")

    # ========================================================================
    # CALCUL DES GREEKS (BLACK-SCHOLES)
    # ========================================================================

    async def calculate_greeks(
        self,
        underlying_price: Decimal,
        strike_price: Decimal,
        time_to_expiry_days: int,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType = OptionType.CALL,
        use_implied_vol: bool = True,
        metadata: Optional[Dict] = None
    ) -> GreeksResult:
        """
        Calcule les Greeks d'une option.

        Args:
            underlying_price: Prix du sous-jacent
            strike_price: Prix d'exercice
            time_to_expiry_days: Jours jusqu'à l'expiration
            risk_free_rate: Taux sans risque
            volatility: Volatilité
            option_type: Type d'option
            use_implied_vol: Utiliser la volatilité implicite
            metadata: Métadonnées

        Returns:
            Résultat des Greeks
        """
        try:
            option_id = uuid4()
            self._metrics["total_calculations"] += 1
            self._metrics["last_calculation"] = datetime.now().isoformat()

            type_key = option_type.value
            if type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][type_key] = 0
            self._metrics["by_type"][type_key] += 1

            # Conversion
            S = float(underlying_price)
            K = float(strike_price)
            T = time_to_expiry_days / self.DAYS_PER_YEAR
            r = risk_free_rate
            sigma = volatility

            # Calcul de la volatilité implicite si demandé
            if use_implied_vol and self._has_option_price():
                implied_vol = await self._calculate_implied_volatility(
                    S, K, T, r, option_type
                )
                sigma = implied_vol if implied_vol else sigma

            # Black-Scholes
            d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)

            # Delta
            if option_type == OptionType.CALL:
                delta = stats.norm.cdf(d1)
            else:
                delta = stats.norm.cdf(d1) - 1

            # Gamma (identique pour call et put)
            gamma = stats.norm.pdf(d1) / (S * sigma * math.sqrt(T))

            # Theta
            theta = -S * stats.norm.pdf(d1) * sigma / (2 * math.sqrt(T))
            theta -= r * K * math.exp(-r * T) * stats.norm.cdf(d2)
            if option_type == OptionType.PUT:
                theta += r * K * math.exp(-r * T)

            # Vega
            vega = S * stats.norm.pdf(d1) * math.sqrt(T)

            # Rho
            if option_type == OptionType.CALL:
                rho = K * T * math.exp(-r * T) * stats.norm.cdf(d2) / 100
            else:
                rho = -K * T * math.exp(-r * T) * stats.norm.cdf(-d2) / 100

            # Prix de l'option
            if option_type == OptionType.CALL:
                option_price = S * stats.norm.cdf(d1) - K * math.exp(-r * T) * stats.norm.cdf(d2)
            else:
                option_price = K * math.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)

            result = GreeksResult(
                option_id=option_id,
                underlying_price=underlying_price,
                strike_price=strike_price,
                time_to_expiry=T,
                risk_free_rate=r,
                volatility=sigma,
                option_type=option_type,
                delta=delta,
                gamma=gamma,
                theta=theta / self.DAYS_PER_YEAR,  # Theta par jour
                vega=vega / 100,  # Vega par point de volatilité
                rho=rho,
                implied_volatility=sigma if use_implied_vol else 0,
                option_price=option_price,
                metadata=metadata or {}
            )

            self._greeks_cache[option_id] = result
            return result

        except Exception as e:
            logger.error(f"Erreur de calcul des Greeks: {e}")
            raise

    async def _calculate_implied_volatility(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: OptionType
    ) -> Optional[float]:
        """
        Calcule la volatilité implicite.

        Args:
            S: Prix du sous-jacent
            K: Prix d'exercice
            T: Temps jusqu'à l'expiration
            r: Taux sans risque
            option_type: Type d'option

        Returns:
            Volatilité implicite
        """
        try:
            # Pour l'exemple, on retourne une valeur simulée
            # En production, utiliser les prix du marché
            return 0.25 + 0.05 * np.random.random()

        except Exception as e:
            logger.error(f"Erreur de calcul de volatilité implicite: {e}")
            return None

    def _has_option_price(self) -> bool:
        """
        Vérifie si un prix d'option est disponible.

        Returns:
            True si disponible
        """
        # En production, vérifier la présence de données de marché
        return True

    # ========================================================================
    # MÉTRIQUES D'OPTIONS
    # ========================================================================

    async def get_option_metrics(
        self,
        option_id: UUID,
        underlying_price: Decimal,
        metadata: Optional[Dict] = None
    ) -> OptionMetrics:
        """
        Calcule les métriques d'une option.

        Args:
            option_id: ID de l'option
            underlying_price: Prix du sous-jacent
            metadata: Métadonnées

        Returns:
            Métriques d'options
        """
        try:
            greeks = self._greeks_cache.get(option_id)
            if not greeks:
                raise ValueError(f"Option {option_id} non trouvée")

            S = float(underlying_price)
            K = float(greeks.strike_price)

            # Valeur intrinsèque
            if greeks.option_type == OptionType.CALL:
                intrinsic_value = max(Decimal(str(S - K)), Decimal("0"))
            else:
                intrinsic_value = max(Decimal(str(K - S)), Decimal("0"))

            # Valeur temps
            time_value = Decimal(str(greeks.option_price)) - intrinsic_value

            # Moneyness
            moneyness = S / K

            # Probabilité ITM/OTM
            d2 = (math.log(S / K) + (greeks.risk_free_rate - 0.5 * greeks.volatility ** 2) * greeks.time_to_expiry) / (greeks.volatility * math.sqrt(greeks.time_to_expiry))
            
            if greeks.option_type == OptionType.CALL:
                prob_itm = stats.norm.cdf(d2)
            else:
                prob_itm = stats.norm.cdf(-d2)
            
            prob_otm = 1 - prob_itm

            # Valeur attendue
            expected_value = Decimal(str(greeks.option_price))

            # Paiement attendu
            expected_payoff = expected_value * Decimal(str(prob_itm))

            # Rank de volatilité implicite
            implied_vol_rank = await self._get_implied_vol_rank(greeks.option_id)

            # Volatilité historique
            hist_vol = await self._get_historical_volatility(greeks.option_id)

            metrics = OptionMetrics(
                option_id=option_id,
                intrinsic_value=intrinsic_value,
                time_value=time_value,
                moneyness=moneyness,
                probability_itm=prob_itm,
                probability_otm=prob_otm,
                expected_value=expected_value,
                expected_payoff=expected_payoff,
                implied_volatility_rank=implied_vol_rank,
                historical_volatility=hist_vol,
                volatility_spread=greeks.volatility - hist_vol,
                metadata=metadata or {}
            )

            self._metrics_cache[option_id] = metrics
            return metrics

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques d'options: {e}")
            raise

    # ========================================================================
    # ANALYSE DE HEDGE
    # ========================================================================

    async def analyze_hedge(
        self,
        portfolio_value: Decimal,
        option_id: UUID,
        hedge_ratio: float = 1.0,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyse un hedge avec options.

        Args:
            portfolio_value: Valeur du portefeuille
            option_id: ID de l'option
            hedge_ratio: Ratio de hedge
            metadata: Métadonnées

        Returns:
            Analyse de hedge
        """
        try:
            greeks = self._greeks_cache.get(option_id)
            if not greeks:
                raise ValueError(f"Option {option_id} non trouvée")

            # Nombre d'options nécessaires pour le hedge
            delta = greeks.delta
            options_needed = (float(portfolio_value) / float(greeks.underlying_price)) * hedge_ratio / abs(delta)

            # Coût du hedge
            hedge_cost = options_needed * greeks.option_price

            # PnL du hedge
            pnl_scenarios = await self._simulate_hedge_pnl(greeks, options_needed)

            return {
                "option_id": str(option_id),
                "portfolio_value": str(portfolio_value),
                "options_needed": options_needed,
                "hedge_cost": hedge_cost,
                "delta": delta,
                "gamma": greeks.gamma,
                "vega": greeks.vega,
                "theta": greeks.theta,
                "pnl_scenarios": pnl_scenarios,
                "hedge_ratio": hedge_ratio,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur d'analyse de hedge: {e}")
            return {"error": str(e)}

    async def _simulate_hedge_pnl(
        self,
        greeks: GreeksResult,
        options_needed: float
    ) -> Dict[str, float]:
        """
        Simule le PnL du hedge.

        Args:
            greeks: Résultat des Greeks
            options_needed: Nombre d'options nécessaires

        Returns:
            Scénarios de PnL
        """
        # Simulation de différents scénarios
        scenarios = {}
        price_changes = [-0.2, -0.1, -0.05, 0, 0.05, 0.1, 0.2]
        
        for change in price_changes:
            new_price = float(greeks.underlying_price) * (1 + change)
            pnl = options_needed * (new_price - float(greeks.underlying_price)) * greeks.delta
            scenarios[f"{change*100:+.0f}%"] = pnl

        return scenarios

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def _get_implied_vol_rank(self, option_id: UUID) -> float:
        """
        Récupère le rank de volatilité implicite.

        Args:
            option_id: ID de l'option

        Returns:
            Rank de volatilité implicite
        """
        # Simulation
        return 0.5 + 0.3 * np.random.random()

    async def _get_historical_volatility(self, option_id: UUID) -> float:
        """
        Récupère la volatilité historique.

        Args:
            option_id: ID de l'option

        Returns:
            Volatilité historique
        """
        # Simulation
        return 0.3 + 0.1 * np.random.random()

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
                "cached_greeks": len(self._greeks_cache),
                "cached_metrics": len(self._metrics_cache),
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
        logger.info("Fermeture de DeltaCalculator...")
        self._greeks_cache.clear()
        self._metrics_cache.clear()
        self._volatility_cache.clear()
        logger.info("DeltaCalculator fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_delta_calculator(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> DeltaCalculator:
    """
    Crée une instance de DeltaCalculator.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de DeltaCalculator
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return DeltaCalculator(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "OptionType",
    "OptionStyle",
    "GreeksType",
    "GreeksResult",
    "OptionMetrics",
    "DeltaCalculator",
    "create_delta_calculator"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du DeltaCalculator."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT DELTA CALCULATOR")
    print("=" * 60)

    # Création du calculateur
    calculator = create_delta_calculator()

    print(f"\n✅ DeltaCalculator initialisé")

    # Calcul des Greeks
    print(f"\n📊 Calcul des Greeks...")
    greeks = await calculator.calculate_greeks(
        underlying_price=Decimal("100"),
        strike_price=Decimal("105"),
        time_to_expiry_days=30,
        risk_free_rate=0.02,
        volatility=0.25,
        option_type=OptionType.CALL
    )

    print(f"   Delta: {greeks.delta:.4f}")
    print(f"   Gamma: {greeks.gamma:.4f}")
    print(f"   Theta: {greeks.theta:.4f}")
    print(f"   Vega: {greeks.vega:.4f}")
    print(f"   Rho: {greeks.rho:.4f}")
    print(f"   Implied Vol: {greeks.implied_volatility:.4f}")
    print(f"   Option Price: {greeks.option_price:.4f}")

    # Calcul des Greeks pour un Put
    print(f"\n📊 Calcul des Greeks pour un Put...")
    greeks_put = await calculator.calculate_greeks(
        underlying_price=Decimal("100"),
        strike_price=Decimal("95"),
        time_to_expiry_days=30,
        risk_free_rate=0.02,
        volatility=0.25,
        option_type=OptionType.PUT
    )

    print(f"   Delta Put: {greeks_put.delta:.4f}")
    print(f"   Option Price: {greeks_put.option_price:.4f}")

    # Métriques d'options
    print(f"\n📈 Métriques d'options...")
    metrics = await calculator.get_option_metrics(
        option_id=greeks.option_id,
        underlying_price=Decimal("102")
    )

    print(f"   Valeur intrinsèque: ${metrics.intrinsic_value}")
    print(f"   Valeur temps: ${metrics.time_value}")
    print(f"   Moneyness: {metrics.moneyness:.3f}")
    print(f"   Probabilité ITM: {metrics.probability_itm:.2%}")
    print(f"   Volatilité historique: {metrics.historical_volatility:.2%}")

    # Analyse de hedge
    print(f"\n🔒 Analyse de hedge...")
    hedge = await calculator.analyze_hedge(
        portfolio_value=Decimal("100000"),
        option_id=greeks.option_id,
        hedge_ratio=0.8
    )

    print(f"   Options nécessaires: {hedge['options_needed']:.0f}")
    print(f"   Coût du hedge: ${hedge['hedge_cost']:.2f}")

    # Scénarios de PnL
    print(f"   Scénarios de PnL:")
    for scenario, pnl in hedge.get('pnl_scenarios', {}).items():
        print(f"      {scenario}: ${pnl:.2f}")

    # Santé du service
    health = await calculator.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Calculs: {health['total_calculations']}")
    print(f"   Greeks en cache: {health['cached_greeks']}")

    # Fermeture
    await calculator.close()

    print("\n" + "=" * 60)
    print("DeltaCalculator NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
