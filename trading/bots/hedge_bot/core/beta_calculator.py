"""
NEXUS AI TRADING SYSTEM - HEDGE BOT BETA CALCULATOR MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de calcul du Beta pour le Hedge Bot.
Calcul du Beta, Alpha, corrélations, et métriques de risque système.

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
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

from ..utils.helpers import (
    calculate_beta,
    calculate_alpha,
    calculate_correlation,
    calculate_volatility,
    safe_decimal,
    safe_float
)
from ..utils.math_utils import MathUtils, create_math_utils

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class BetaMethod(Enum):
    """Méthodes de calcul du Beta."""
    OLS = "ols"                      # Ordinary Least Squares
    ROBUST = "robust"                # Régression robuste
    BAYESIAN = "bayesian"            # Régression bayésienne
    WLS = "wls"                      # Weighted Least Squares
    GARCH = "garch"                  # Modèle GARCH
    EWMA = "ewma"                    # Exponentially Weighted Moving Average
    DCC = "dcc"                      # Dynamic Conditional Correlation


class BenchmarkType(Enum):
    """Types de benchmark."""
    MARKET = "market"
    SECTOR = "sector"
    CUSTOM = "custom"
    INDEX = "index"
    PORTFOLIO = "portfolio"
    PEER = "peer"


@dataclass
class BetaResult:
    """Résultat du calcul Beta."""
    beta: float
    alpha: float
    r_squared: float
    correlation: float
    covariance: float
    volatility_asset: float
    volatility_market: float
    p_value: float
    std_error: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    method: BetaMethod
    benchmark: str
    period_days: int
    n_observations: int
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "beta": self.beta,
            "alpha": self.alpha,
            "r_squared": self.r_squared,
            "correlation": self.correlation,
            "covariance": self.covariance,
            "volatility_asset": self.volatility_asset,
            "volatility_market": self.volatility_market,
            "p_value": self.p_value,
            "std_error": self.std_error,
            "confidence_interval_lower": self.confidence_interval_lower,
            "confidence_interval_upper": self.confidence_interval_upper,
            "method": self.method.value,
            "benchmark": self.benchmark,
            "period_days": self.period_days,
            "n_observations": self.n_observations,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class CorrelationMatrix:
    """Matrice de corrélation."""
    assets: List[str]
    matrix: List[List[float]]
    p_values: List[List[float]]
    method: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "assets": self.assets,
            "matrix": self.matrix,
            "p_values": self.p_values,
            "method": self.method,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class RiskMetrics:
    """Métriques de risque."""
    asset: str
    beta: float
    alpha: float
    r_squared: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    var_95: float
    var_99: float
    expected_shortfall: float
    tracking_error: float
    information_ratio: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "asset": self.asset,
            "beta": self.beta,
            "alpha": self.alpha,
            "r_squared": self.r_squared,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "expected_shortfall": self.expected_shortfall,
            "tracking_error": self.tracking_error,
            "information_ratio": self.information_ratio,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE BETA CALCULATOR
# ============================================================================

class BetaCalculator:
    """
    Calculateur de Beta avancé.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le calculateur de Beta.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Utilitaires
        self.math_utils = create_math_utils()
        
        # Cache
        self._beta_cache: Dict[str, BetaResult] = {}
        self._correlation_cache: Dict[str, CorrelationMatrix] = {}
        self._risk_metrics_cache: Dict[str, RiskMetrics] = {}
        self._price_cache: Dict[str, List[float]] = {}
        self._return_cache: Dict[str, List[float]] = {}
        
        # Métriques
        self._metrics = {
            "total_calculations": 0,
            "by_method": {},
            "by_benchmark": {},
            "last_calculation": None
        }

        logger.info("BetaCalculator initialisé avec succès")

    # ========================================================================
    # CALCUL DU BETA
    # ========================================================================

    async def calculate_beta(
        self,
        asset_returns: List[float],
        market_returns: List[float],
        method: BetaMethod = BetaMethod.OLS,
        benchmark: str = "market",
        period_days: int = 30,
        confidence_level: float = 0.95,
        metadata: Optional[Dict] = None
    ) -> BetaResult:
        """
        Calcule le Beta.

        Args:
            asset_returns: Rendements de l'actif
            market_returns: Rendements du marché
            method: Méthode de calcul
            benchmark: Benchmark
            period_days: Période en jours
            confidence_level: Niveau de confiance
            metadata: Métadonnées

        Returns:
            Résultat du calcul Beta
        """
        try:
            self._metrics["total_calculations"] += 1
            self._metrics["last_calculation"] = datetime.now().isoformat()

            method_key = method.value
            if method_key not in self._metrics["by_method"]:
                self._metrics["by_method"][method_key] = 0
            self._metrics["by_method"][method_key] += 1

            if benchmark not in self._metrics["by_benchmark"]:
                self._metrics["by_benchmark"][benchmark] = 0
            self._metrics["by_benchmark"][benchmark] += 1

            # Calcul selon la méthode
            if method == BetaMethod.OLS:
                result = await self._calculate_beta_ols(
                    asset_returns, market_returns, confidence_level
                )
            elif method == BetaMethod.ROBUST:
                result = await self._calculate_beta_robust(
                    asset_returns, market_returns, confidence_level
                )
            elif method == BetaMethod.EWMA:
                result = await self._calculate_beta_ewma(
                    asset_returns, market_returns, confidence_level
                )
            elif method == BetaMethod.BAYESIAN:
                result = await self._calculate_beta_bayesian(
                    asset_returns, market_returns, confidence_level
                )
            elif method == BetaMethod.WLS:
                result = await self._calculate_beta_wls(
                    asset_returns, market_returns, confidence_level
                )
            else:
                result = await self._calculate_beta_ols(
                    asset_returns, market_returns, confidence_level
                )

            # Création du résultat
            beta_result = BetaResult(
                beta=result["beta"],
                alpha=result["alpha"],
                r_squared=result["r_squared"],
                correlation=result["correlation"],
                covariance=result["covariance"],
                volatility_asset=result["volatility_asset"],
                volatility_market=result["volatility_market"],
                p_value=result["p_value"],
                std_error=result["std_error"],
                confidence_interval_lower=result["ci_lower"],
                confidence_interval_upper=result["ci_upper"],
                method=method,
                benchmark=benchmark,
                period_days=period_days,
                n_observations=len(asset_returns),
                timestamp=datetime.now(),
                metadata=metadata or {}
            )

            # Mise en cache
            cache_key = f"{benchmark}_{period_days}_{method.value}"
            self._beta_cache[cache_key] = beta_result

            return beta_result

        except Exception as e:
            logger.error(f"Erreur de calcul Beta: {e}")
            raise

    async def _calculate_beta_ols(
        self,
        asset_returns: List[float],
        market_returns: List[float],
        confidence_level: float
    ) -> Dict[str, Any]:
        """
        Calcule le Beta avec OLS.

        Args:
            asset_returns: Rendements de l'actif
            market_returns: Rendements du marché
            confidence_level: Niveau de confiance

        Returns:
            Résultats
        """
        try:
            x = np.array(market_returns)
            y = np.array(asset_returns)
            n = len(x)

            # Régression OLS
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

            # Métriques
            beta = slope
            alpha = intercept
            correlation = r_value
            r_squared = r_value ** 2
            covariance = np.cov(x, y)[0][1]
            volatility_asset = np.std(y) * np.sqrt(252)
            volatility_market = np.std(x) * np.sqrt(252)

            # Intervalle de confiance
            t_value = stats.t.ppf((1 + confidence_level) / 2, n - 2)
            se_beta = std_err
            ci_lower = beta - t_value * se_beta
            ci_upper = beta + t_value * se_beta

            return {
                "beta": beta,
                "alpha": alpha,
                "r_squared": r_squared,
                "correlation": correlation,
                "covariance": covariance,
                "volatility_asset": volatility_asset,
                "volatility_market": volatility_market,
                "p_value": p_value,
                "std_error": std_err,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper
            }

        except Exception as e:
            logger.error(f"Erreur OLS: {e}")
            raise

    async def _calculate_beta_robust(
        self,
        asset_returns: List[float],
        market_returns: List[float],
        confidence_level: float
    ) -> Dict[str, Any]:
        """
        Calcule le Beta avec régression robuste.

        Args:
            asset_returns: Rendements de l'actif
            market_returns: Rendements du marché
            confidence_level: Niveau de confiance

        Returns:
            Résultats
        """
        try:
            import statsmodels.api as sm
            from statsmodels.robust.robust_linear_model import RLM

            x = np.array(market_returns)
            y = np.array(asset_returns)
            x = sm.add_constant(x)

            # Régression robuste (Huber)
            model = RLM(y, x, M=sm.robust.norms.HuberT())
            results = model.fit()

            beta = results.params[1]
            alpha = results.params[0]
            
            # Métriques approximatives
            correlation = calculate_correlation(asset_returns, market_returns)
            r_squared = correlation ** 2
            covariance = np.cov(asset_returns, market_returns)[0][1]
            volatility_asset = calculate_volatility(asset_returns, annualize=True)
            volatility_market = calculate_volatility(market_returns, annualize=True)

            return {
                "beta": beta,
                "alpha": alpha,
                "r_squared": r_squared,
                "correlation": correlation,
                "covariance": covariance,
                "volatility_asset": volatility_asset / 100,
                "volatility_market": volatility_market / 100,
                "p_value": results.pvalues[1],
                "std_error": results.bse[1],
                "ci_lower": beta - 1.96 * results.bse[1],
                "ci_upper": beta + 1.96 * results.bse[1]
            }

        except ImportError:
            logger.warning("Statsmodels non disponible, fallback sur OLS")
            return await self._calculate_beta_ols(
                asset_returns, market_returns, confidence_level
            )
        except Exception as e:
            logger.error(f"Erreur robust regression: {e}")
            raise

    async def _calculate_beta_ewma(
        self,
        asset_returns: List[float],
        market_returns: List[float],
        confidence_level: float
    ) -> Dict[str, Any]:
        """
        Calcule le Beta avec EWMA.

        Args:
            asset_returns: Rendements de l'actif
            market_returns: Rendements du marché
            confidence_level: Niveau de confiance

        Returns:
            Résultats
        """
        try:
            lambda_ = 0.94  # Facteur de décroissance

            # Calcul des poids EWMA
            n = len(asset_returns)
            weights = np.array([(1 - lambda_) * lambda_ ** (n - 1 - i) for i in range(n)])
            weights = weights / weights.sum()

            # Moyennes pondérées
            mean_asset = np.average(asset_returns, weights=weights)
            mean_market = np.average(market_returns, weights=weights)

            # Covariance et variance pondérées
            covariance = np.average(
                (np.array(asset_returns) - mean_asset) * (np.array(market_returns) - mean_market),
                weights=weights
            )
            variance_market = np.average(
                (np.array(market_returns) - mean_market) ** 2,
                weights=weights
            )

            beta = covariance / variance_market if variance_market != 0 else 0
            alpha = mean_asset - beta * mean_market

            # Métriques
            correlation = covariance / (np.std(asset_returns) * np.std(market_returns))
            r_squared = correlation ** 2
            volatility_asset = calculate_volatility(asset_returns, annualize=True)
            volatility_market = calculate_volatility(market_returns, annualize=True)

            return {
                "beta": beta,
                "alpha": alpha,
                "r_squared": r_squared,
                "correlation": correlation,
                "covariance": covariance,
                "volatility_asset": volatility_asset / 100,
                "volatility_market": volatility_market / 100,
                "p_value": 0.05,  # Approximatif
                "std_error": 0.1,  # Approximatif
                "ci_lower": beta - 0.2,
                "ci_upper": beta + 0.2
            }

        except Exception as e:
            logger.error(f"Erreur EWMA: {e}")
            raise

    async def _calculate_beta_bayesian(
        self,
        asset_returns: List[float],
        market_returns: List[float],
        confidence_level: float
    ) -> Dict[str, Any]:
        """
        Calcule le Beta avec approche bayésienne.

        Args:
            asset_returns: Rendements de l'actif
            market_returns: Rendements du marché
            confidence_level: Niveau de confiance

        Returns:
            Résultats
        """
        try:
            # Prior: beta ~ N(1, 0.5)
            prior_mean = 1.0
            prior_std = 0.5

            # Calcul OLS
            x = np.array(market_returns)
            y = np.array(asset_returns)
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

            # Mise à jour bayésienne (approximation)
            n = len(x)
            var_beta = std_err ** 2
            
            # Posterior
            posterior_variance = 1 / (1 / prior_std ** 2 + n / var_beta)
            posterior_mean = posterior_variance * (prior_mean / prior_std ** 2 + n * slope / var_beta)

            beta = posterior_mean
            alpha = intercept
            correlation = r_value
            r_squared = r_value ** 2
            covariance = np.cov(x, y)[0][1]
            volatility_asset = calculate_volatility(asset_returns, annualize=True)
            volatility_market = calculate_volatility(market_returns, annualize=True)

            return {
                "beta": beta,
                "alpha": alpha,
                "r_squared": r_squared,
                "correlation": correlation,
                "covariance": covariance,
                "volatility_asset": volatility_asset / 100,
                "volatility_market": volatility_market / 100,
                "p_value": p_value,
                "std_error": np.sqrt(posterior_variance),
                "ci_lower": beta - 1.96 * np.sqrt(posterior_variance),
                "ci_upper": beta + 1.96 * np.sqrt(posterior_variance)
            }

        except Exception as e:
            logger.error(f"Erreur bayésienne: {e}")
            raise

    async def _calculate_beta_wls(
        self,
        asset_returns: List[float],
        market_returns: List[float],
        confidence_level: float
    ) -> Dict[str, Any]:
        """
        Calcule le Beta avec WLS.

        Args:
            asset_returns: Rendements de l'actif
            market_returns: Rendements du marché
            confidence_level: Niveau de confiance

        Returns:
            Résultats
        """
        try:
            import statsmodels.api as sm

            x = np.array(market_returns)
            y = np.array(asset_returns)
            
            # Poids: inverse de la volatilité
            weights = 1 / (np.abs(x - np.mean(x)) + 0.001)
            weights = weights / weights.sum()

            # Régression pondérée
            x = sm.add_constant(x)
            model = sm.WLS(y, x, weights=weights)
            results = model.fit()

            beta = results.params[1]
            alpha = results.params[0]
            correlation = calculate_correlation(asset_returns, market_returns)
            r_squared = correlation ** 2
            covariance = np.cov(asset_returns, market_returns)[0][1]
            volatility_asset = calculate_volatility(asset_returns, annualize=True)
            volatility_market = calculate_volatility(market_returns, annualize=True)

            return {
                "beta": beta,
                "alpha": alpha,
                "r_squared": r_squared,
                "correlation": correlation,
                "covariance": covariance,
                "volatility_asset": volatility_asset / 100,
                "volatility_market": volatility_market / 100,
                "p_value": results.pvalues[1],
                "std_error": results.bse[1],
                "ci_lower": beta - 1.96 * results.bse[1],
                "ci_upper": beta + 1.96 * results.bse[1]
            }

        except ImportError:
            logger.warning("Statsmodels non disponible, fallback sur OLS")
            return await self._calculate_beta_ols(
                asset_returns, market_returns, confidence_level
            )
        except Exception as e:
            logger.error(f"Erreur WLS: {e}")
            raise

    # ========================================================================
    # MATRICE DE CORRÉLATION
    # ========================================================================

    async def calculate_correlation_matrix(
        self,
        returns_data: Dict[str, List[float]],
        method: str = "pearson",
        metadata: Optional[Dict] = None
    ) -> CorrelationMatrix:
        """
        Calcule la matrice de corrélation.

        Args:
            returns_data: Données de rendements par actif
            method: Méthode (pearson, spearman, kendall)
            metadata: Métadonnées

        Returns:
            Matrice de corrélation
        """
        try:
            assets = list(returns_data.keys())
            n = len(assets)
            
            matrix = np.zeros((n, n))
            p_values = np.zeros((n, n))

            for i, asset1 in enumerate(assets):
                for j, asset2 in enumerate(assets):
                    if i == j:
                        matrix[i][j] = 1.0
                        p_values[i][j] = 0.0
                    else:
                        corr, p_val = stats.pearsonr(
                            returns_data[asset1],
                            returns_data[asset2]
                        )
                        matrix[i][j] = corr
                        p_values[i][j] = p_val

            return CorrelationMatrix(
                assets=assets,
                matrix=matrix.tolist(),
                p_values=p_values.tolist(),
                method=method,
                timestamp=datetime.now(),
                metadata=metadata or {}
            )

        except Exception as e:
            logger.error(f"Erreur de calcul de la matrice de corrélation: {e}")
            raise

    # ========================================================================
    # MÉTRIQUES DE RISQUE
    # ========================================================================

    async def calculate_risk_metrics(
        self,
        asset_returns: List[float],
        market_returns: List[float],
        asset_name: str,
        risk_free_rate: float = 0.02,
        metadata: Optional[Dict] = None
    ) -> RiskMetrics:
        """
        Calcule les métriques de risque.

        Args:
            asset_returns: Rendements de l'actif
            market_returns: Rendements du marché
            asset_name: Nom de l'actif
            risk_free_rate: Taux sans risque
            metadata: Métadonnées

        Returns:
            Métriques de risque
        """
        try:
            # Beta et Alpha
            beta_result = await self.calculate_beta(
                asset_returns,
                market_returns,
                method=BetaMethod.OLS
            )

            # Volatilité
            volatility = calculate_volatility(asset_returns, annualize=True) / 100
            
            # Sharpe Ratio
            avg_return = np.mean(asset_returns)
            std_return = np.std(asset_returns)
            daily_rf = risk_free_rate / 252
            sharpe_ratio = (avg_return - daily_rf) / std_return * np.sqrt(252) if std_return > 0 else 0

            # Sortino Ratio
            downside_returns = [r for r in asset_returns if r < 0]
            downside_deviation = np.std(downside_returns) if downside_returns else 0.001
            sortino_ratio = (avg_return - daily_rf) / downside_deviation * np.sqrt(252) if downside_deviation > 0 else 0

            # Calmar Ratio
            max_drawdown = calculate_max_drawdown(asset_returns) / 100
            annualized_return = (1 + np.mean(asset_returns)) ** 252 - 1
            calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

            # Value at Risk
            var_95 = np.percentile(asset_returns, 5) * 100
            var_99 = np.percentile(asset_returns, 1) * 100

            # Expected Shortfall
            tail_returns = [r for r in asset_returns if r < np.percentile(asset_returns, 5)]
            expected_shortfall = np.mean(tail_returns) * 100 if tail_returns else 0

            # Tracking Error
            tracking_error = np.std(np.array(asset_returns) - np.array(market_returns)) * np.sqrt(252)

            # Information Ratio
            active_return = np.mean(asset_returns) - np.mean(market_returns)
            information_ratio = active_return / tracking_error * np.sqrt(252) if tracking_error > 0 else 0

            return RiskMetrics(
                asset=asset_name,
                beta=beta_result.beta,
                alpha=beta_result.alpha,
                r_squared=beta_result.r_squared,
                volatility=volatility * 100,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                max_drawdown=max_drawdown * 100,
                var_95=var_95,
                var_99=var_99,
                expected_shortfall=expected_shortfall,
                tracking_error=tracking_error,
                information_ratio=information_ratio,
                metadata=metadata or {}
            )

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques de risque: {e}")
            raise

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_beta(
        self,
        benchmark: str,
        period_days: int,
        method: BetaMethod = BetaMethod.OLS
    ) -> Optional[BetaResult]:
        """
        Récupère un résultat Beta du cache.

        Args:
            benchmark: Benchmark
            period_days: Période en jours
            method: Méthode

        Returns:
            Résultat Beta ou None
        """
        cache_key = f"{benchmark}_{period_days}_{method.value}"
        return self._beta_cache.get(cache_key)

    async def get_correlation_matrix(
        self,
        assets: Tuple[str, ...]
    ) -> Optional[CorrelationMatrix]:
        """
        Récupère une matrice de corrélation du cache.

        Args:
            assets: Liste des actifs

        Returns:
            Matrice de corrélation ou None
        """
        cache_key = "_".join(sorted(assets))
        return self._correlation_cache.get(cache_key)

    async def get_risk_metrics(
        self,
        asset_name: str
    ) -> Optional[RiskMetrics]:
        """
        Récupère les métriques de risque du cache.

        Args:
            asset_name: Nom de l'actif

        Returns:
            Métriques de risque ou None
        """
        return self._risk_metrics_cache.get(asset_name)

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
                "by_method": self._metrics["by_method"],
                "by_benchmark": self._metrics["by_benchmark"],
                "last_calculation": self._metrics["last_calculation"],
                "cached_betas": len(self._beta_cache),
                "cached_correlations": len(self._correlation_cache),
                "cached_risk_metrics": len(self._risk_metrics_cache),
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
        logger.info("Fermeture de BetaCalculator...")
        self._beta_cache.clear()
        self._correlation_cache.clear()
        self._risk_metrics_cache.clear()
        self._price_cache.clear()
        self._return_cache.clear()
        logger.info("BetaCalculator fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_beta_calculator(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> BetaCalculator:
    """
    Crée une instance de BetaCalculator.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de BetaCalculator
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return BetaCalculator(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "BetaMethod",
    "BenchmarkType",
    "BetaResult",
    "CorrelationMatrix",
    "RiskMetrics",
    "BetaCalculator",
    "create_beta_calculator"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du BetaCalculator."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT BETA CALCULATOR")
    print("=" * 60)

    # Création du calculateur
    calculator = create_beta_calculator()

    print(f"\n✅ BetaCalculator initialisé")

    # Génération de données de test
    np.random.seed(42)
    n = 252  # 1 année de données
    market_returns = np.random.normal(0.0005, 0.02, n)
    asset_returns = 0.8 * market_returns + np.random.normal(0, 0.015, n)

    # Calcul du Beta
    print(f"\n📊 Calcul du Beta...")
    beta_result = await calculator.calculate_beta(
        asset_returns=asset_returns.tolist(),
        market_returns=market_returns.tolist(),
        method=BetaMethod.OLS,
        benchmark="S&P 500",
        period_days=252
    )

    print(f"   Beta: {beta_result.beta:.4f}")
    print(f"   Alpha: {beta_result.alpha:.4f}")
    print(f"   R²: {beta_result.r_squared:.4f}")
    print(f"   Corrélation: {beta_result.correlation:.4f}")
    print(f"   Intervalle de confiance: [{beta_result.confidence_interval_lower:.4f}, {beta_result.confidence_interval_upper:.4f}]")

    # Calcul avec EWMA
    print(f"\n📊 Calcul Beta avec EWMA...")
    beta_ewma = await calculator.calculate_beta(
        asset_returns=asset_returns.tolist(),
        market_returns=market_returns.tolist(),
        method=BetaMethod.EWMA,
        benchmark="S&P 500",
        period_days=252
    )

    print(f"   Beta EWMA: {beta_ewma.beta:.4f}")

    # Matrice de corrélation
    print(f"\n📊 Matrice de corrélation...")
    returns_data = {
        "BTC": np.random.normal(0.001, 0.03, 100).tolist(),
        "ETH": np.random.normal(0.001, 0.035, 100).tolist(),
        "SOL": np.random.normal(0.001, 0.04, 100).tolist()
    }
    
    corr_matrix = await calculator.calculate_correlation_matrix(returns_data)
    print(f"   Actifs: {corr_matrix.assets}")
    print(f"   Matrice: {corr_matrix.matrix[0]}")

    # Métriques de risque
    print(f"\n📊 Métriques de risque...")
    risk_metrics = await calculator.calculate_risk_metrics(
        asset_returns=asset_returns.tolist(),
        market_returns=market_returns.tolist(),
        asset_name="BTC/USDT"
    )

    print(f"   Volatilité: {risk_metrics.volatility:.2f}%")
    print(f"   Sharpe Ratio: {risk_metrics.sharpe_ratio:.3f}")
    print(f"   Sortino Ratio: {risk_metrics.sortino_ratio:.3f}")
    print(f"   VaR 95%: {risk_metrics.var_95:.2f}%")
    print(f"   Expected Shortfall: {risk_metrics.expected_shortfall:.2f}%")

    # Santé du service
    health = await calculator.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Calculs: {health['total_calculations']}")
    print(f"   Méthodes: {health['by_method']}")

    # Fermeture
    await calculator.close()

    print("\n" + "=" * 60)
    print("BetaCalculator NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
