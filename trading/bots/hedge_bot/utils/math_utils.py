"""
NEXUS AI TRADING SYSTEM - HEDGE BOT MATH UTILS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'utilitaires mathématiques avancés pour le Hedge Bot.
Support des calculs statistiques, financiers, et d'optimisation.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import math
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats, optimize, interpolate
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm, t, chi2, f, linregress

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class DistributionType(Enum):
    """Types de distributions."""
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    T = "t"
    CHI2 = "chi2"
    F = "f"
    EXPONENTIAL = "exponential"
    POISSON = "poisson"
    BINOMIAL = "binomial"
    UNIFORM = "uniform"
    CAUCHY = "cauchy"
    WEIBULL = "weibull"
    GAMMA = "gamma"
    BETA = "beta"


class OptimizationMethod(Enum):
    """Méthodes d'optimisation."""
    GRADIENT_DESCENT = "gradient_descent"
    NEWTON = "newton"
    BFGS = "bfgs"
    LBFGS = "lbfgs"
    SLSQP = "slsqp"
    COBYLA = "cobyla"
    DIFFERENTIAL_EVOLUTION = "differential_evolution"
    SIMULATED_ANNEALING = "simulated_annealing"
    PARTICLE_SWARM = "particle_swarm"
    GENETIC = "genetic"


@dataclass
class ConfidenceInterval:
    """Intervalle de confiance."""
    lower: float
    upper: float
    confidence: float
    mean: float
    std: float
    method: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "lower": self.lower,
            "upper": self.upper,
            "confidence": self.confidence,
            "mean": self.mean,
            "std": self.std,
            "method": self.method,
            "metadata": self.metadata
        }


@dataclass
class RegressionResult:
    """Résultat de régression."""
    slope: float
    intercept: float
    r_value: float
    p_value: float
    std_err: float
    r_squared: float
    adj_r_squared: float
    residuals: List[float]
    predicted: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "slope": self.slope,
            "intercept": self.intercept,
            "r_value": self.r_value,
            "p_value": self.p_value,
            "std_err": self.std_err,
            "r_squared": self.r_squared,
            "adj_r_squared": self.adj_r_squared,
            "residuals": self.residuals,
            "predicted": self.predicted,
            "metadata": self.metadata
        }


@dataclass
class OptimizationResult:
    """Résultat d'optimisation."""
    x: np.ndarray
    fun: float
    nit: int
    nfev: int
    success: bool
    message: str
    jac: Optional[np.ndarray] = None
    hess: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "x": self.x.tolist(),
            "fun": self.fun,
            "nit": self.nit,
            "nfev": self.nfev,
            "success": self.success,
            "message": self.message,
            "jac": self.jac.tolist() if self.jac is not None else None,
            "hess": self.hess.tolist() if self.hess is not None else None,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE MATH UTILS
# ============================================================================

class MathUtils:
    """
    Utilitaires mathématiques avancés.
    """

    def __init__(
        self,
        precision: int = 10,
        random_seed: Optional[int] = None
    ):
        """
        Initialise les utilitaires mathématiques.

        Args:
            precision: Précision des calculs
            random_seed: Seed pour la reproductibilité
        """
        self.precision = precision
        self.random_seed = random_seed
        
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # Cache
        self._distribution_cache: Dict[str, Any] = {}
        self._optimization_cache: Dict[str, Any] = {}
        
        # Métriques
        self._metrics = {
            "total_calculations": 0,
            "by_type": {},
            "last_calculation": None
        }

        logger.info("MathUtils initialisé avec succès")

    # ========================================================================
    # STATISTIQUES DE BASE
    # ========================================================================

    def mean(self, data: List[float]) -> float:
        """
        Calcule la moyenne.

        Args:
            data: Données

        Returns:
            Moyenne
        """
        self._update_metrics("mean")
        if not data:
            return 0.0
        return np.mean(data)

    def median(self, data: List[float]) -> float:
        """
        Calcule la médiane.

        Args:
            data: Données

        Returns:
            Médiane
        """
        self._update_metrics("median")
        if not data:
            return 0.0
        return np.median(data)

    def mode(self, data: List[float]) -> float:
        """
        Calcule le mode.

        Args:
            data: Données

        Returns:
            Mode
        """
        self._update_metrics("mode")
        if not data:
            return 0.0
        return stats.mode(data)[0][0]

    def variance(self, data: List[float], ddof: int = 1) -> float:
        """
        Calcule la variance.

        Args:
            data: Données
            ddof: Degrés de liberté

        Returns:
            Variance
        """
        self._update_metrics("variance")
        if len(data) < 2:
            return 0.0
        return np.var(data, ddof=ddof)

    def std(self, data: List[float], ddof: int = 1) -> float:
        """
        Calcule l'écart-type.

        Args:
            data: Données
            ddof: Degrés de liberté

        Returns:
            Écart-type
        """
        self._update_metrics("std")
        if len(data) < 2:
            return 0.0
        return np.std(data, ddof=ddof)

    def skewness(self, data: List[float]) -> float:
        """
        Calcule l'asymétrie.

        Args:
            data: Données

        Returns:
            Asymétrie
        """
        self._update_metrics("skewness")
        if len(data) < 3:
            return 0.0
        return stats.skew(data)

    def kurtosis(self, data: List[float]) -> float:
        """
        Calcule le kurtosis.

        Args:
            data: Données

        Returns:
            Kurtosis
        """
        self._update_metrics("kurtosis")
        if len(data) < 4:
            return 0.0
        return stats.kurtosis(data)

    # ========================================================================
    # PERCENTILES ET QUANTILES
    # ========================================================================

    def percentile(self, data: List[float], p: float) -> float:
        """
        Calcule un percentile.

        Args:
            data: Données
            p: Percentile (0-100)

        Returns:
            Percentile
        """
        self._update_metrics("percentile")
        if not data:
            return 0.0
        return np.percentile(data, p)

    def quantile(self, data: List[float], q: float) -> float:
        """
        Calcule un quantile.

        Args:
            data: Données
            q: Quantile (0-1)

        Returns:
            Quantile
        """
        self._update_metrics("quantile")
        if not data:
            return 0.0
        return np.quantile(data, q)

    def iqr(self, data: List[float]) -> float:
        """
        Calcule l'intervalle interquartile.

        Args:
            data: Données

        Returns:
            IQR
        """
        self._update_metrics("iqr")
        if len(data) < 4:
            return 0.0
        q75 = np.percentile(data, 75)
        q25 = np.percentile(data, 25)
        return q75 - q25

    # ========================================================================
    # TESTS STATISTIQUES
    # ========================================================================

    def t_test(self, data: List[float], mu: float = 0) -> Tuple[float, float]:
        """
        Test t de Student.

        Args:
            data: Données
            mu: Moyenne théorique

        Returns:
            (statistic, p_value)
        """
        self._update_metrics("t_test")
        if len(data) < 2:
            return 0.0, 1.0
        result = stats.ttest_1samp(data, mu)
        return result.statistic, result.pvalue

    def t_test_two_samples(
        self,
        data1: List[float],
        data2: List[float],
        equal_var: bool = True
    ) -> Tuple[float, float]:
        """
        Test t de Student pour deux échantillons.

        Args:
            data1: Premier échantillon
            data2: Deuxième échantillon
            equal_var: Variances égales

        Returns:
            (statistic, p_value)
        """
        self._update_metrics("t_test_two_samples")
        if len(data1) < 2 or len(data2) < 2:
            return 0.0, 1.0
        result = stats.ttest_ind(data1, data2, equal_var=equal_var)
        return result.statistic, result.pvalue

    def chi2_test(self, observed: List[float], expected: Optional[List[float]] = None) -> Tuple[float, float]:
        """
        Test du chi-carré.

        Args:
            observed: Fréquences observées
            expected: Fréquences attendues

        Returns:
            (statistic, p_value)
        """
        self._update_metrics("chi2_test")
        if not observed:
            return 0.0, 1.0
        if expected is None:
            expected = [sum(observed) / len(observed)] * len(observed)
        result = stats.chisquare(observed, expected)
        return result.statistic, result.pvalue

    def shapiro_wilk(self, data: List[float]) -> Tuple[float, float]:
        """
        Test de normalité de Shapiro-Wilk.

        Args:
            data: Données

        Returns:
            (statistic, p_value)
        """
        self._update_metrics("shapiro_wilk")
        if len(data) < 3 or len(data) > 5000:
            return 0.0, 1.0
        result = stats.shapiro(data)
        return result.statistic, result.pvalue

    def kolmogorov_smirnov(self, data: List[float], cdf: str = "norm") -> Tuple[float, float]:
        """
        Test de Kolmogorov-Smirnov.

        Args:
            data: Données
            cdf: Distribution de référence

        Returns:
            (statistic, p_value)
        """
        self._update_metrics("kolmogorov_smirnov")
        if len(data) < 2:
            return 0.0, 1.0
        result = stats.kstest(data, cdf)
        return result.statistic, result.pvalue

    # ========================================================================
    # DISTRIBUTIONS
    # ========================================================================

    def normal_pdf(self, x: float, mean: float = 0, std: float = 1) -> float:
        """
        Fonction de densité de la distribution normale.

        Args:
            x: Point
            mean: Moyenne
            std: Écart-type

        Returns:
            Densité
        """
        self._update_metrics("normal_pdf")
        return norm.pdf(x, mean, std)

    def normal_cdf(self, x: float, mean: float = 0, std: float = 1) -> float:
        """
        Fonction de répartition de la distribution normale.

        Args:
            x: Point
            mean: Moyenne
            std: Écart-type

        Returns:
            Probabilité
        """
        self._update_metrics("normal_cdf")
        return norm.cdf(x, mean, std)

    def normal_ppf(self, p: float, mean: float = 0, std: float = 1) -> float:
        """
        Quantile de la distribution normale.

        Args:
            p: Probabilité
            mean: Moyenne
            std: Écart-type

        Returns:
            Quantile
        """
        self._update_metrics("normal_ppf")
        return norm.ppf(p, mean, std)

    def confidence_interval(
        self,
        data: List[float],
        confidence: float = 0.95,
        method: str = "t"
    ) -> ConfidenceInterval:
        """
        Calcule un intervalle de confiance.

        Args:
            data: Données
            confidence: Niveau de confiance
            method: Méthode (t, z, bootstrap)

        Returns:
            Intervalle de confiance
        """
        self._update_metrics("confidence_interval")
        if len(data) < 2:
            return ConfidenceInterval(
                lower=0.0,
                upper=0.0,
                confidence=confidence,
                mean=0.0,
                std=0.0,
                method=method
            )

        mean = np.mean(data)
        std = np.std(data, ddof=1)
        n = len(data)
        sem = std / np.sqrt(n)

        if method == "t":
            dof = n - 1
            t_val = t.ppf((1 + confidence) / 2, dof)
            margin = t_val * sem
        elif method == "z":
            z_val = norm.ppf((1 + confidence) / 2)
            margin = z_val * sem
        elif method == "bootstrap":
            # Bootstrap simplifié
            n_bootstrap = 1000
            boot_means = []
            for _ in range(n_bootstrap):
                sample = np.random.choice(data, size=n, replace=True)
                boot_means.append(np.mean(sample))
            lower = np.percentile(boot_means, (1 - confidence) / 2 * 100)
            upper = np.percentile(boot_means, (1 + confidence) / 2 * 100)
            return ConfidenceInterval(
                lower=lower,
                upper=upper,
                confidence=confidence,
                mean=mean,
                std=std,
                method=method
            )
        else:
            raise ValueError(f"Méthode non supportée: {method}")

        return ConfidenceInterval(
            lower=mean - margin,
            upper=mean + margin,
            confidence=confidence,
            mean=mean,
            std=std,
            method=method
        )

    # ========================================================================
    # RÉGRESSION ET CORRÉLATION
    # ========================================================================

    def correlation(
        self,
        x: List[float],
        y: List[float],
        method: str = "pearson"
    ) -> float:
        """
        Calcule la corrélation.

        Args:
            x: Première variable
            y: Deuxième variable
            method: pearson, spearman, kendall

        Returns:
            Corrélation
        """
        self._update_metrics("correlation")
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        if method == "pearson":
            return stats.pearsonr(x, y)[0]
        elif method == "spearman":
            return stats.spearmanr(x, y)[0]
        elif method == "kendall":
            return stats.kendalltau(x, y)[0]
        else:
            raise ValueError(f"Méthode non supportée: {method}")

    def linear_regression(
        self,
        x: List[float],
        y: List[float]
    ) -> RegressionResult:
        """
        Régression linéaire.

        Args:
            x: Variable indépendante
            y: Variable dépendante

        Returns:
            Résultat de régression
        """
        self._update_metrics("linear_regression")
        if len(x) != len(y) or len(x) < 2:
            return RegressionResult(
                slope=0.0,
                intercept=0.0,
                r_value=0.0,
                p_value=1.0,
                std_err=0.0,
                r_squared=0.0,
                adj_r_squared=0.0,
                residuals=[],
                predicted=[]
            )

        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        
        # Prédictions et résidus
        predicted = [intercept + slope * xi for xi in x]
        residuals = [yi - pi for yi, pi in zip(y, predicted)]
        
        # R² ajusté
        n = len(x)
        r_squared = r_value ** 2
        adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - 2) if n > 2 else r_squared

        return RegressionResult(
            slope=slope,
            intercept=intercept,
            r_value=r_value,
            p_value=p_value,
            std_err=std_err,
            r_squared=r_squared,
            adj_r_squared=adj_r_squared,
            residuals=residuals,
            predicted=predicted
        )

    def polynomial_regression(
        self,
        x: List[float],
        y: List[float],
        degree: int = 2
    ) -> Dict[str, Any]:
        """
        Régression polynomiale.

        Args:
            x: Variable indépendante
            y: Variable dépendante
            degree: Degré du polynôme

        Returns:
            Résultat de régression
        """
        self._update_metrics("polynomial_regression")
        if len(x) != len(y) or len(x) < degree + 1:
            return {}

        coeffs = np.polyfit(x, y, degree)
        poly = np.poly1d(coeffs)
        predicted = poly(x)
        residuals = [yi - pi for yi, pi in zip(y, predicted)]
        
        # R²
        ss_res = sum(r ** 2 for r in residuals)
        ss_tot = sum((yi - np.mean(y)) ** 2 for yi in y)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "coefficients": coeffs.tolist(),
            "polynomial": poly,
            "predicted": predicted.tolist(),
            "residuals": residuals,
            "r_squared": r_squared,
            "degree": degree
        }

    # ========================================================================
    # OPTIMISATION
    # ========================================================================

    def optimize_scalar(
        self,
        func: Callable,
        bounds: Tuple[float, float],
        method: str = "brent",
        maxiter: int = 1000
    ) -> Dict[str, Any]:
        """
        Optimisation scalaire.

        Args:
            func: Fonction à optimiser
            bounds: Bornes
            method: Méthode (brent, golden, bounded)
            maxiter: Nombre d'itérations maximum

        Returns:
            Résultat d'optimisation
        """
        self._update_metrics("optimize_scalar")
        
        if method == "brent":
            result = optimize.minimize_scalar(func, method='brent', options={'maxiter': maxiter})
        elif method == "golden":
            result = optimize.minimize_scalar(func, method='golden', options={'maxiter': maxiter})
        elif method == "bounded":
            result = optimize.minimize_scalar(func, method='bounded', bounds=bounds, options={'maxiter': maxiter})
        else:
            raise ValueError(f"Méthode non supportée: {method}")

        return {
            "x": result.x,
            "fun": result.fun,
            "nit": result.nit,
            "nfev": result.nfev,
            "success": result.success,
            "message": result.message
        }

    def optimize_vector(
        self,
        func: Callable,
        x0: List[float],
        bounds: Optional[List[Tuple[float, float]]] = None,
        method: OptimizationMethod = OptimizationMethod.BFGS,
        constraints: Optional[List[Dict]] = None,
        maxiter: int = 1000
    ) -> OptimizationResult:
        """
        Optimisation vectorielle.

        Args:
            func: Fonction à optimiser
            x0: Point initial
            bounds: Bornes
            method: Méthode d'optimisation
            constraints: Contraintes
            maxiter: Nombre d'itérations maximum

        Returns:
            Résultat d'optimisation
        """
        self._update_metrics("optimize_vector")
        
        x0 = np.array(x0)
        n = len(x0)
        
        if bounds is None:
            bounds = [(-np.inf, np.inf)] * n

        method_map = {
            OptimizationMethod.BFGS: 'BFGS',
            OptimizationMethod.LBFGS: 'L-BFGS-B',
            OptimizationMethod.SLSQP: 'SLSQP',
            OptimizationMethod.COBYLA: 'COBYLA',
            OptimizationMethod.NEWTON: 'Newton-CG',
            OptimizationMethod.GRADIENT_DESCENT: 'CG'
        }

        scipy_method = method_map.get(method, 'BFGS')
        
        if method == OptimizationMethod.DIFFERENTIAL_EVOLUTION:
            result = differential_evolution(
                func,
                bounds,
                maxiter=maxiter,
                popsize=15
            )
        else:
            result = minimize(
                func,
                x0,
                method=scipy_method,
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': maxiter}
            )

        return OptimizationResult(
            x=result.x,
            fun=result.fun,
            nit=result.nit,
            nfev=result.nfev,
            success=result.success,
            message=result.message,
            jac=result.jac if hasattr(result, 'jac') else None,
            hess=result.hess if hasattr(result, 'hess') else None
        )

    # ========================================================================
    # SÉRIES TEMPORELLES
    # ========================================================================

    def autocorrelation(
        self,
        data: List[float],
        lag: int = 1
    ) -> float:
        """
        Calcule l'autocorrélation.

        Args:
            data: Données
            lag: Décalage

        Returns:
            Autocorrélation
        """
        self._update_metrics("autocorrelation")
        if len(data) <= lag:
            return 0.0
        
        n = len(data)
        mean = np.mean(data)
        
        numerator = sum((data[i] - mean) * (data[i - lag] - mean) for i in range(lag, n))
        denominator = sum((data[i] - mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator

    def partial_autocorrelation(
        self,
        data: List[float],
        lag: int = 1
    ) -> float:
        """
        Calcule l'autocorrélation partielle.

        Args:
            data: Données
            lag: Décalage

        Returns:
            Autocorrélation partielle
        """
        self._update_metrics("partial_autocorrelation")
        if len(data) <= lag:
            return 0.0
        
        # Méthode de Durbin-Levinson
        n = len(data)
        mean = np.mean(data)
        centered = [x - mean for x in data]
        
        if lag == 1:
            return self.autocorrelation(data, 1)
        
        # Pour lag > 1, utiliser l'approche récursive
        pacf = [0.0] * (lag + 1)
        pacf[1] = self.autocorrelation(data, 1)
        
        for k in range(2, lag + 1):
            phi = [0.0] * (k + 1)
            phi[1] = pacf[1]
            
            for i in range(2, k + 1):
                numerator = self.autocorrelation(data, i)
                for j in range(1, i):
                    numerator -= phi[j] * self.autocorrelation(data, i - j)
                denominator = 1 - sum(phi[j] * self.autocorrelation(data, i - j) for j in range(1, i))
                phi[i] = numerator / denominator if denominator != 0 else 0
                
                for j in range(1, i):
                    phi[j] = phi[j] - phi[i] * phi[i - j]
            
            pacf[k] = phi[k]
        
        return pacf[lag]

    def moving_average(
        self,
        data: List[float],
        window: int,
        weights: Optional[List[float]] = None
    ) -> List[float]:
        """
        Calcule la moyenne mobile.

        Args:
            data: Données
            window: Taille de la fenêtre
            weights: Poids (optionnel)

        Returns:
            Moyenne mobile
        """
        self._update_metrics("moving_average")
        if len(data) < window:
            return []
        
        result = []
        if weights is None:
            weights = [1.0 / window] * window
        
        for i in range(len(data) - window + 1):
            window_data = data[i:i + window]
            result.append(sum(w * d for w, d in zip(weights, window_data)))
        
        return result

    def exponential_smoothing(
        self,
        data: List[float],
        alpha: float = 0.3,
        beta: float = 0.1,
        gamma: float = 0.1,
        seasonal_period: int = 7
    ) -> Dict[str, List[float]]:
        """
        Lissage exponentiel.

        Args:
            data: Données
            alpha: Paramètre de lissage
            beta: Paramètre de tendance
            gamma: Paramètre saisonnier
            seasonal_period: Période saisonnière

        Returns:
            Résultat du lissage
        """
        self._update_metrics("exponential_smoothing")
        if not data:
            return {}
        
        n = len(data)
        level = [0.0] * n
        trend = [0.0] * n
        seasonal = [0.0] * (n + seasonal_period)
        forecast = [0.0] * n
        
        # Initialisation
        level[0] = data[0]
        seasonal[:seasonal_period] = [data[i] - level[0] for i in range(min(seasonal_period, n))]
        
        for i in range(1, n):
            # Mise à jour du niveau
            level[i] = alpha * (data[i] - seasonal[i]) + (1 - alpha) * (level[i-1] + trend[i-1])
            
            # Mise à jour de la tendance
            trend[i] = beta * (level[i] - level[i-1]) + (1 - beta) * trend[i-1]
            
            # Mise à jour de la saisonnalité
            if i + seasonal_period < len(seasonal):
                seasonal[i + seasonal_period] = gamma * (data[i] - level[i]) + (1 - gamma) * seasonal[i]
            
            # Prévision
            forecast[i] = level[i-1] + trend[i-1] + seasonal[i]
        
        return {
            "level": level,
            "trend": trend,
            "seasonal": seasonal[:n],
            "forecast": forecast,
            "fitted": [level[i] + trend[i] + seasonal[i] for i in range(n)]
        }

    # ========================================================================
    # ANALYSE DE RISQUE
    # ========================================================================

    def value_at_risk(
        self,
        returns: List[float],
        confidence: float = 0.95,
        method: str = "historical"
    ) -> float:
        """
        Calcule la Value at Risk.

        Args:
            returns: Rendements
            confidence: Niveau de confiance
            method: historical, parametric, monte_carlo

        Returns:
            VaR
        """
        self._update_metrics("value_at_risk")
        if not returns:
            return 0.0
        
        if method == "historical":
            return abs(np.percentile(returns, (1 - confidence) * 100))
        elif method == "parametric":
            mean = np.mean(returns)
            std = np.std(returns)
            z_score = norm.ppf(confidence)
            return abs(mean - z_score * std)
        elif method == "monte_carlo":
            # Simulation Monte Carlo simplifiée
            n_sim = 10000
            mean = np.mean(returns)
            std = np.std(returns)
            sim_returns = np.random.normal(mean, std, n_sim)
            return abs(np.percentile(sim_returns, (1 - confidence) * 100))
        else:
            raise ValueError(f"Méthode non supportée: {method}")

    def expected_shortfall(
        self,
        returns: List[float],
        confidence: float = 0.95
    ) -> float:
        """
        Calcule l'Expected Shortfall.

        Args:
            returns: Rendements
            confidence: Niveau de confiance

        Returns:
            Expected Shortfall
        """
        self._update_metrics("expected_shortfall")
        if not returns:
            return 0.0
        
        var = self.value_at_risk(returns, confidence, "historical")
        tail_returns = [r for r in returns if r < -var]
        
        if not tail_returns:
            return 0.0
        
        return abs(np.mean(tail_returns))

    def maximum_drawdown(self, prices: List[float]) -> float:
        """
        Calcule le maximum drawdown.

        Args:
            prices: Prix

        Returns:
            Maximum drawdown
        """
        self._update_metrics("maximum_drawdown")
        if len(prices) < 2:
            return 0.0
        
        peak = prices[0]
        max_dd = 0.0
        
        for price in prices:
            if price > peak:
                peak = price
            dd = (peak - price) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        return max_dd

    def sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.02
    ) -> float:
        """
        Calcule le Sharpe Ratio.

        Args:
            returns: Rendements
            risk_free_rate: Taux sans risque

        Returns:
            Sharpe Ratio
        """
        self._update_metrics("sharpe_ratio")
        if not returns:
            return 0.0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        daily_rf = risk_free_rate / 365
        sharpe = (avg_return - daily_rf) / std_return
        
        return sharpe * np.sqrt(365)

    def sortino_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.02
    ) -> float:
        """
        Calcule le Sortino Ratio.

        Args:
            returns: Rendements
            risk_free_rate: Taux sans risque

        Returns:
            Sortino Ratio
        """
        self._update_metrics("sortino_ratio")
        if not returns:
            return 0.0
        
        avg_return = np.mean(returns)
        downside_returns = [r for r in returns if r < 0]
        
        if not downside_returns:
            return 0.0
        
        downside_deviation = np.std(downside_returns)
        if downside_deviation == 0:
            return 0.0
        
        daily_rf = risk_free_rate / 365
        sortino = (avg_return - daily_rf) / downside_deviation
        
        return sortino * np.sqrt(365)

    def calmar_ratio(
        self,
        returns: List[float],
        max_drawdown: Optional[float] = None
    ) -> float:
        """
        Calcule le Calmar Ratio.

        Args:
            returns: Rendements
            max_drawdown: Drawdown maximum

        Returns:
            Calmar Ratio
        """
        self._update_metrics("calmar_ratio")
        if not returns:
            return 0.0
        
        annualized_return = self.annualized_return(returns)
        
        if max_drawdown is None:
            # Simulation de drawdown maximum
            max_drawdown = 0.1  # Valeur par défaut
        
        if max_drawdown == 0:
            return 0.0
        
        return annualized_return / max_drawdown

    def annualized_return(self, returns: List[float]) -> float:
        """
        Calcule le rendement annualisé.

        Args:
            returns: Rendements

        Returns:
            Rendement annualisé
        """
        self._update_metrics("annualized_return")
        if not returns:
            return 0.0
        
        total_return = self.cumulative_return(returns)
        n = len(returns)
        days = n
        
        if days > 0:
            annualized = (1 + total_return) ** (365 / days) - 1
            return annualized
        
        return 0.0

    def cumulative_return(self, returns: List[float]) -> float:
        """
        Calcule le rendement cumulé.

        Args:
            returns: Rendements

        Returns:
            Rendement cumulé
        """
        self._update_metrics("cumulative_return")
        if not returns:
            return 0.0
        
        cumulative = 1.0
        for r in returns:
            cumulative *= (1 + r)
        
        return cumulative - 1

    # ========================================================================
    # CALCULS FINANCIERS
    # ========================================================================

    def compound_interest(
        self,
        principal: float,
        rate: float,
        periods: int,
        compounding: int = 1
    ) -> float:
        """
        Calcule les intérêts composés.

        Args:
            principal: Capital initial
            rate: Taux d'intérêt
            periods: Nombre de périodes
            compounding: Fréquence de composition

        Returns:
            Montant final        """
        self._update_metrics("compound_interest")
        return principal * (1 + rate / compounding) ** (periods * compounding)

    def present_value(
        self,
        future_value: float,
        rate: float,
        periods: int
    ) -> float:
        """
        Calcule la valeur présente.

        Args:
            future_value: Valeur future
            rate: Taux d'actualisation
            periods: Nombre de périodes

        Returns:
            Valeur présente
        """
        self._update_metrics("present_value")
        return future_value / (1 + rate) ** periods

    def future_value(
        self,
        present_value: float,
        rate: float,
        periods: int
    ) -> float:
        """
        Calcule la valeur future.

        Args:
            present_value: Valeur présente
            rate: Taux d'intérêt
            periods: Nombre de périodes

        Returns:
            Valeur future
        """
        self._update_metrics("future_value")
        return present_value * (1 + rate) ** periods

    def net_present_value(
        self,
        cashflows: List[float],
        rate: float
    ) -> float:
        """
        Calcule la valeur présente nette.

        Args:
            cashflows: Flux de trésorerie
            rate: Taux d'actualisation

        Returns:
            Valeur présente nette
        """
        self._update_metrics("net_present_value")
        npv = 0.0
        for i, cf in enumerate(cashflows):
            npv += cf / (1 + rate) ** i
        return npv

    def internal_rate_of_return(self, cashflows: List[float]) -> float:
        """
        Calcule le taux de rendement interne.

        Args:
            cashflows: Flux de trésorerie

        Returns:
            TRI
        """
        self._update_metrics("internal_rate_of_return")
        if len(cashflows) < 2:
            return 0.0
        
        try:
            return optimize.newton(lambda r: self.net_present_value(cashflows, r), 0.1)
        except:
            return 0.0

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    def _update_metrics(self, calc_type: str) -> None:
        """
        Met à jour les métriques.

        Args:
            calc_type: Type de calcul
        """
        self._metrics["total_calculations"] += 1
        if calc_type not in self._metrics["by_type"]:
            self._metrics["by_type"][calc_type] = 0
        self._metrics["by_type"][calc_type] += 1
        self._metrics["last_calculation"] = datetime.now().isoformat()

    def get_health(self) -> Dict[str, Any]:
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
                "precision": self.precision,
                "random_seed": self.random_seed,
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
        logger.info("Fermeture de MathUtils...")
        self._distribution_cache.clear()
        self._optimization_cache.clear()
        logger.info("MathUtils fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_math_utils(
    precision: int = 10,
    random_seed: Optional[int] = None
) -> MathUtils:
    """
    Crée une instance de MathUtils.

    Args:
        precision: Précision des calculs
        random_seed: Seed pour la reproductibilité

    Returns:
        Instance de MathUtils
    """
    return MathUtils(
        precision=precision,
        random_seed=random_seed
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "DistributionType",
    "OptimizationMethod",
    "ConfidenceInterval",
    "RegressionResult",
    "OptimizationResult",
    "MathUtils",
    "create_math_utils"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation de MathUtils."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT MATH UTILS")
    print("=" * 60)

    # Création de l'instance
    math_utils = create_math_utils(random_seed=42)

    # Données de test
    data = [1.2, 2.3, 3.4, 4.5, 5.6, 6.7, 7.8, 8.9, 9.0, 10.1]
    returns = [0.01, -0.005, 0.02, 0.015, -0.01, 0.03, -0.02, 0.025, 0.005, -0.01]

    print(f"\n📊 Statistiques de base:")
    print(f"   Moyenne: {math_utils.mean(data):.2f}")
    print(f"   Médiane: {math_utils.median(data):.2f}")
    print(f"   Écart-type: {math_utils.std(data):.4f}")
    print(f"   Asymétrie: {math_utils.skewness(data):.4f}")
    print(f"   Kurtosis: {math_utils.kurtosis(data):.4f}")

    # Intervalle de confiance
    ci = math_utils.confidence_interval(data, confidence=0.95)
    print(f"\n📈 Intervalle de confiance (95%):")
    print(f"   [{ci.lower:.2f}, {ci.upper:.2f}]")
    print(f"   Moyenne: {ci.mean:.2f}")

    # Régression
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    y = [2, 4, 5, 7, 8, 10, 11, 13, 14, 16]
    regression = math_utils.linear_regression(x, y)
    print(f"\n📐 Régression linéaire:")
    print(f"   Pente: {regression.slope:.4f}")
    print(f"   Ordonnée: {regression.intercept:.4f}")
    print(f"   R²: {regression.r_squared:.4f}")
    print(f"   p-value: {regression.p_value:.4f}")

    # Optimisation
    def func(x): return (x[0] - 2) ** 2 + (x[1] - 3) ** 2
    result = math_utils.optimize_vector(
        func,
        x0=[0, 0],
        method=OptimizationMethod.BFGS
    )
    print(f"\n🎯 Optimisation:")
    print(f"   Solution: {result.x.tolist()}")
    print(f"   Valeur: {result.fun:.6f}")
    print(f"   Succès: {result.success}")

    # Métriques de risque
    print(f"\n⚠️ Métriques de risque:")
    print(f"   VaR 95%: {math_utils.value_at_risk(returns, 0.95):.4f}")
    print(f"   Expected Shortfall: {math_utils.expected_shortfall(returns, 0.95):.4f}")
    print(f"   Sharpe Ratio: {math_utils.sharpe_ratio(returns):.4f}")
    print(f"   Sortino Ratio: {math_utils.sortino_ratio(returns):.4f}")

    # Santé du service
    health = math_utils.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Calculs: {health['total_calculations']}")
    print(f"   Types: {health['by_type']}")

    # Fermeture
    await math_utils.close()

    print("\n" + "=" * 60)
    print("MathUtils NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    from typing import Callable
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
