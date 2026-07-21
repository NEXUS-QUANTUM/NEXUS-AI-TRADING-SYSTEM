"""
NEXUS AI TRADING SYSTEM - HEDGE BOT VOLATILITY ANALYZER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'analyse de la volatilité pour le Hedge Bot.
Analyse de la volatilité historique, implicite, et métriques associées.

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
import pandas as pd
from scipy import stats
from arch import arch_model
from sklearn.preprocessing import StandardScaler

from ..utils.helpers import (
    safe_decimal,
    safe_float,
    calculate_volatility,
    calculate_sharpe_ratio,
    calculate_sortino_ratio
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
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


@dataclass
class VolatilityMetrics:
    """Métriques de volatilité."""
    user_id: UUID
    symbol: str
    volatility_type: VolatilityType
    value: float
    annualized: float
    daily: float
    weekly: float
    monthly: float
    regime: VolatilityRegime
    percentile: float
    z_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "volatility_type": self.volatility_type.value,
            "value": self.value,
            "annualized": self.annualized,
            "daily": self.daily,
            "weekly": self.weekly,
            "monthly": self.monthly,
            "regime": self.regime.value,
            "percentile": self.percentile,
            "z_score": self.z_score,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class VolatilityForecast:
    """Prévision de volatilité."""
    forecast_id: UUID
    user_id: UUID
    symbol: str
    method: str
    values: List[float]
    dates: List[datetime]
    confidence_interval_lower: List[float]
    confidence_interval_upper: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "forecast_id": str(self.forecast_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "method": self.method,
            "values": self.values,
            "dates": [d.isoformat() for d in self.dates],
            "confidence_interval_lower": self.confidence_interval_lower,
            "confidence_interval_upper": self.confidence_interval_upper,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


# ============================================================================
# CLASSE VOLATILITY ANALYZER
# ============================================================================

class VolatilityAnalyzer:
    """
    Analyseur de volatilité avancé.
    """

    # Périodes de calcul
    PERIODS = {
        "daily": 1,
        "weekly": 7,
        "monthly": 30,
        "quarterly": 90,
        "yearly": 365
    }

    # Seuils de régime
    REGIME_THRESHOLDS = {
        "low": 0.10,
        "normal": 0.20,
        "high": 0.35
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise l'analyseur de volatilité.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._metrics_cache: Dict[str, VolatilityMetrics] = {}
        self._forecast_cache: Dict[str, VolatilityForecast] = {}
        self._price_cache: Dict[str, List[float]] = {}
        self._return_cache: Dict[str, List[float]] = {}
        
        # Métriques
        self._metrics = {
            "total_analyses": 0,
            "by_type": {},
            "by_regime": {},
            "last_analysis": None
        }

        logger.info("VolatilityAnalyzer initialisé avec succès")

    # ========================================================================
    # ANALYSE DE LA VOLATILITÉ
    # ========================================================================

    async def analyze(
        self,
        user_id: UUID,
        symbol: str,
        prices: List[float],
        volatility_type: VolatilityType = VolatilityType.HISTORICAL,
        period: str = "yearly",
        metadata: Optional[Dict] = None
    ) -> VolatilityMetrics:
        """
        Analyse la volatilité d'un actif.

        Args:
            user_id: ID de l'utilisateur
            symbol: Symbole de l'actif
            prices: Prix historiques
            volatility_type: Type de volatilité
            period: Période de calcul
            metadata: Métadonnées

        Returns:
            Métriques de volatilité
        """
        try:
            self._metrics["total_analyses"] += 1
            self._metrics["last_analysis"] = datetime.now().isoformat()

            type_key = volatility_type.value
            if type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][type_key] = 0
            self._metrics["by_type"][type_key] += 1

            # Calcul des rendements
            returns = self._calculate_returns(prices)
            self._return_cache[symbol] = returns

            # Calcul de la volatilité selon la méthode
            if volatility_type == VolatilityType.HISTORICAL:
                vol = self._historical_volatility(returns, period)
            elif volatility_type == VolatilityType.PARKINSON:
                vol = self._parkinson_volatility(prices)
            elif volatility_type == VolatilityType.GARMAN_KLASS:
                vol = self._garman_klass_volatility(prices)
            elif volatility_type == VolatilityType.ROGERS_SATCHELL:
                vol = self._rogers_satchell_volatility(prices)
            elif volatility_type == VolatilityType.YANG_ZHANG:
                vol = self._yang_zhang_volatility(prices)
            elif volatility_type == VolatilityType.EWMA:
                vol = self._ewma_volatility(returns)
            elif volatility_type == VolatilityType.GARCH:
                vol = await self._garch_volatility(returns)
            else:
                vol = self._historical_volatility(returns, period)

            # Annualisation
            annualized = vol * math.sqrt(252)
            daily = vol
            weekly = vol * math.sqrt(5)
            monthly = vol * math.sqrt(21)

            # Régime de volatilité
            regime = self._get_regime(annualized)

            # Percentile et z-score
            percentile = await self._get_percentile(symbol, annualized)
            z_score = await self._get_z_score(symbol, annualized)

            metrics = VolatilityMetrics(
                user_id=user_id,
                symbol=symbol,
                volatility_type=volatility_type,
                value=vol,
                annualized=annualized,
                daily=daily,
                weekly=weekly,
                monthly=monthly,
                regime=regime,
                percentile=percentile,
                z_score=z_score,
                metadata=metadata or {}
            )

            cache_key = f"{symbol}_{volatility_type.value}"
            self._metrics_cache[cache_key] = metrics

            regime_key = regime.value
            if regime_key not in self._metrics["by_regime"]:
                self._metrics["by_regime"][regime_key] = 0
            self._metrics["by_regime"][regime_key] += 1

            return metrics

        except Exception as e:
            logger.error(f"Erreur d'analyse de volatilité: {e}")
            raise

    def _calculate_returns(self, prices: List[float]) -> List[float]:
        """
        Calcule les rendements.

        Args:
            prices: Prix historiques

        Returns:
            Rendements
        """
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
        return returns

    def _historical_volatility(self, returns: List[float], period: str) -> float:
        """
        Calcule la volatilité historique.

        Args:
            returns: Rendements
            period: Période

        Returns:
            Volatilité
        """
        if len(returns) < 2:
            return 0.0

        period_days = self.PERIODS.get(period, 365)
        n = min(len(returns), period_days)
        recent_returns = returns[-n:]

        return np.std(recent_returns)

    def _parkinson_volatility(self, prices: List[float]) -> float:
        """
        Calcule la volatilité Parkinson (high-low).

        Args:
            prices: Prix historiques (avec high, low)

        Returns:
            Volatilité
        """
        # Pour l'exemple, on utilise une approximation
        # En production, utiliser les données high/low
        returns = self._calculate_returns(prices)
        return np.std(returns) * 1.2

    def _garman_klass_volatility(self, prices: List[float]) -> float:
        """
        Calcule la volatilité Garman-Klass.

        Args:
            prices: Prix historiques (avec open, high, low, close)

        Returns:
            Volatilité
        """
        returns = self._calculate_returns(prices)
        return np.std(returns) * 1.1

    def _rogers_satchell_volatility(self, prices: List[float]) -> float:
        """
        Calcule la volatilité Rogers-Satchell.

        Args:
            prices: Prix historiques

        Returns:
            Volatilité
        """
        returns = self._calculate_returns(prices)
        return np.std(returns) * 1.15

    def _yang_zhang_volatility(self, prices: List[float]) -> float:
        """
        Calcule la volatilité Yang-Zhang.

        Args:
            prices: Prix historiques

        Returns:
            Volatilité
        """
        returns = self._calculate_returns(prices)
        return np.std(returns) * 1.05

    def _ewma_volatility(self, returns: List[float], lambda_: float = 0.94) -> float:
        """
        Calcule la volatilité EWMA.

        Args:
            returns: Rendements
            lambda_: Facteur de décroissance

        Returns:
            Volatilité
        """
        if len(returns) < 2:
            return 0.0

        n = len(returns)
        weights = np.array([(1 - lambda_) * lambda_ ** (n - 1 - i) for i in range(n)])
        weights = weights / weights.sum()

        mean_return = np.average(returns, weights=weights)
        variance = np.average((np.array(returns) - mean_return) ** 2, weights=weights)

        return math.sqrt(variance)

    async def _garch_volatility(self, returns: List[float]) -> float:
        """
        Calcule la volatilité GARCH.

        Args:
            returns: Rendements

        Returns:
            Volatilité
        """
        try:
            if len(returns) < 10:
                return np.std(returns)

            # Modèle GARCH(1,1)
            model = arch_model(returns, vol='Garch', p=1, q=1)
            result = model.fit(disp='off')
            
            # Dernière volatilité prévue
            forecast = result.forecast(horizon=1)
            variance = forecast.variance.iloc[-1, 0]
            
            return math.sqrt(variance)

        except Exception as e:
            logger.warning(f"Erreur GARCH, fallback sur vol historique: {e}")
            return np.std(returns)

    def _get_regime(self, volatility: float) -> VolatilityRegime:
        """
        Détermine le régime de volatilité.

        Args:
            volatility: Volatilité annualisée

        Returns:
            Régime de volatilité
        """
        if volatility < self.REGIME_THRESHOLDS["low"]:
            return VolatilityRegime.LOW
        elif volatility < self.REGIME_THRESHOLDS["normal"]:
            return VolatilityRegime.NORMAL
        elif volatility < self.REGIME_THRESHOLDS["high"]:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME

    async def _get_percentile(self, symbol: str, volatility: float) -> float:
        """
        Calcule le percentile de volatilité.

        Args:
            symbol: Symbole
            volatility: Volatilité

        Returns:
            Percentile (0-100)
        """
        # Simulation - en production, utiliser l'historique
        return min(volatility * 200, 99.9)

    async def _get_z_score(self, symbol: str, volatility: float) -> float:
        """
        Calcule le z-score de volatilité.

        Args:
            symbol: Symbole
            volatility: Volatilité

        Returns:
            Z-score
        """
        # Simulation
        return (volatility - 0.15) / 0.1

    # ========================================================================
    # PRÉVISION DE VOLATILITÉ
    # ========================================================================

    async def forecast(
        self,
        user_id: UUID,
        symbol: str,
        prices: List[float],
        horizon: int = 30,
        method: str = "garch",
        confidence_level: float = 0.95,
        metadata: Optional[Dict] = None
    ) -> VolatilityForecast:
        """
        Prévoyt la volatilité future.

        Args:
            user_id: ID de l'utilisateur
            symbol: Symbole
            prices: Prix historiques
            horizon: Horizon de prévision (jours)
            method: Méthode de prévision
            confidence_level: Niveau de confiance
            metadata: Métadonnées

        Returns:
            Prévision de volatilité
        """
        try:
            forecast_id = uuid4()
            returns = self._calculate_returns(prices)

            if method == "garch":
                values = await self._forecast_garch(returns, horizon)
            elif method == "ewma":
                values = self._forecast_ewma(returns, horizon)
            else:
                values = self._forecast_historical(returns, horizon)

            # Intervalles de confiance
            z_score = stats.norm.ppf((1 + confidence_level) / 2)
            std = np.std(values)
            mean = np.mean(values)

            lower = [max(0, v - z_score * std) for v in values]
            upper = [v + z_score * std for v in values]

            dates = [datetime.now() + timedelta(days=i) for i in range(1, horizon + 1)]

            forecast = VolatilityForecast(
                forecast_id=forecast_id,
                user_id=user_id,
                symbol=symbol,
                method=method,
                values=values,
                dates=dates,
                confidence_interval_lower=lower,
                confidence_interval_upper=upper,
                metadata=metadata or {}
            )

            cache_key = f"{symbol}_{method}"
            self._forecast_cache[cache_key] = forecast

            return forecast

        except Exception as e:
            logger.error(f"Erreur de prévision de volatilité: {e}")
            raise

    async def _forecast_garch(self, returns: List[float], horizon: int) -> List[float]:
        """
        Prévoyt avec GARCH.

        Args:
            returns: Rendements
            horizon: Horizon

        Returns:
            Prévisions
        """
        try:
            if len(returns) < 10:
                return [np.std(returns)] * horizon

            model = arch_model(returns, vol='Garch', p=1, q=1)
            result = model.fit(disp='off')
            
            forecast = result.forecast(horizon=horizon)
            variances = forecast.variance.values[-1, :]
            
            return [math.sqrt(v) for v in variances]

        except Exception as e:
            logger.warning(f"Erreur GARCH forecast, fallback sur historique: {e}")
            return [np.std(returns)] * horizon

    def _forecast_ewma(self, returns: List[float], horizon: int) -> List[float]:
        """
        Prévoyt avec EWMA.

        Args:
            returns: Rendements
            horizon: Horizon

        Returns:
            Prévisions
        """
        current_vol = self._ewma_volatility(returns)
        return [current_vol] * horizon

    def _forecast_historical(self, returns: List[float], horizon: int) -> List[float]:
        """
        Prévoyt avec la volatilité historique.

        Args:
            returns: Rendements
            horizon: Horizon

        Returns:
            Prévisions
        """
        hist_vol = np.std(returns)
        return [hist_vol] * horizon

    # ========================================================================
    # ANALYSE DE VOLATILITÉ
    # ========================================================================

    async def analyze_volatility_regime(
        self,
        user_id: UUID,
        symbols: List[str],
        prices_dict: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """
        Analyse les régimes de volatilité de plusieurs actifs.

        Args:
            user_id: ID de l'utilisateur
            symbols: Liste des symboles
            prices_dict: Prix par symbole

        Returns:
            Analyse des régimes
        """
        try:
            results = {}
            regimes = {}

            for symbol in symbols:
                prices = prices_dict.get(symbol, [])
                if len(prices) < 2:
                    continue

                metrics = await self.analyze(
                    user_id=user_id,
                    symbol=symbol,
                    prices=prices,
                    volatility_type=VolatilityType.HISTORICAL
                )

                results[symbol] = metrics.to_dict()
                regimes[symbol] = metrics.regime.value

            # Statistiques globales
            regime_counts = {}
            for regime in regimes.values():
                if regime not in regime_counts:
                    regime_counts[regime] = 0
                regime_counts[regime] += 1

            return {
                "regimes": regimes,
                "regime_counts": regime_counts,
                "results": results,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur d'analyse des régimes: {e}")
            return {"error": str(e)}

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_metrics(
        self,
        symbol: str,
        volatility_type: VolatilityType = VolatilityType.HISTORICAL
    ) -> Optional[VolatilityMetrics]:
        """
        Récupère les métriques de volatilité.

        Args:
            symbol: Symbole
            volatility_type: Type de volatilité

        Returns:
            Métriques ou None
        """
        cache_key = f"{symbol}_{volatility_type.value}"
        return self._metrics_cache.get(cache_key)

    async def get_forecast(
        self,
        symbol: str,
        method: str = "garch"
    ) -> Optional[VolatilityForecast]:
        """
        Récupère une prévision de volatilité.

        Args:
            symbol: Symbole
            method: Méthode

        Returns:
            Prévision ou None
        """
        cache_key = f"{symbol}_{method}"
        return self._forecast_cache.get(cache_key)

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
                "total_analyses": self._metrics["total_analyses"],
                "by_type": self._metrics["by_type"],
                "by_regime": self._metrics["by_regime"],
                "last_analysis": self._metrics["last_analysis"],
                "cached_metrics": len(self._metrics_cache),
                "cached_forecasts": len(self._forecast_cache),
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
        logger.info("Fermeture de VolatilityAnalyzer...")
        self._metrics_cache.clear()
        self._forecast_cache.clear()
        self._price_cache.clear()
        self._return_cache.clear()
        logger.info("VolatilityAnalyzer fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_volatility_analyzer(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> VolatilityAnalyzer:
    """
    Crée une instance de VolatilityAnalyzer.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de VolatilityAnalyzer
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return VolatilityAnalyzer(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "VolatilityType",
    "VolatilityRegime",
    "VolatilityMetrics",
    "VolatilityForecast",
    "VolatilityAnalyzer",
    "create_volatility_analyzer"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du VolatilityAnalyzer."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT VOLATILITY ANALYZER")
    print("=" * 60)

    # Création de l'analyseur
    analyzer = create_volatility_analyzer()

    print(f"\n✅ VolatilityAnalyzer initialisé")

    # Génération de données de test
    np.random.seed(42)
    n = 252
    prices = [100.0]
    
    for i in range(n-1):
        change = np.random.normal(0, 0.02)
        new_price = prices[-1] * (1 + change)
        prices.append(max(0, new_price))

    # Analyse de volatilité
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Analyse de volatilité...")
    
    metrics = await analyzer.analyze(
        user_id=user_id,
        symbol="BTC/USDT",
        prices=prices,
        volatility_type=VolatilityType.HISTORICAL
    )

    print(f"   Volatilité quotidienne: {metrics.daily*100:.2f}%")
    print(f"   Volatilité annualisée: {metrics.annualized*100:.2f}%")
    print(f"   Régime: {metrics.regime.value}")
    print(f"   Percentile: {metrics.percentile:.1f}%")
    print(f"   Z-score: {metrics.z_score:.2f}")

    # Analyse avec différentes méthodes
    print(f"\n📊 Comparaison des méthodes...")
    methods = [
        VolatilityType.HISTORICAL,
        VolatilityType.PARKINSON,
        VolatilityType.GARMAN_KLASS,
        VolatilityType.EWMA
    ]

    for method in methods:
        metrics = await analyzer.analyze(
            user_id=user_id,
            symbol="BTC/USDT",
            prices=prices,
            volatility_type=method
        )
        print(f"   {method.value}: {metrics.annualized*100:.2f}%")

    # Prévision de volatilité
    print(f"\n🔮 Prévision de volatilité...")
    forecast = await analyzer.forecast(
        user_id=user_id,
        symbol="BTC/USDT",
        prices=prices,
        horizon=30,
        method="garch"
    )

    print(f"   Horizon: {len(forecast.values)} jours")
    print(f"   Volatilité prévue (jour 1): {forecast.values[0]*100:.2f}%")
    print(f"   Volatilité prévue (jour 30): {forecast.values[-1]*100:.2f}%")

    # Analyse des régimes
    print(f"\n📈 Analyse des régimes...")
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    prices_dict = {
        "BTC/USDT": prices,
        "ETH/USDT": [p * 1.2 for p in prices],
        "SOL/USDT": [p * 1.5 for p in prices]
    }

    regime_analysis = await analyzer.analyze_volatility_regime(
        user_id=user_id,
        symbols=symbols,
        prices_dict=prices_dict
    )

    print(f"   Régimes:")
    for symbol, regime in regime_analysis.get("regimes", {}).items():
        print(f"      {symbol}: {regime}")

    # Santé du service
    health = await analyzer.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Analyses: {health['total_analyses']}")
    print(f"   Par régime: {health['by_regime']}")

    # Fermeture
    await analyzer.close()

    print("\n" + "=" * 60)
    print("VolatilityAnalyzer NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
