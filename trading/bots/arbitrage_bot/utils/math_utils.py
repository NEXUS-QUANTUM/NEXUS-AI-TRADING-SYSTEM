"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Math Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires mathématiques pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import math
import random
import statistics
import numpy as np
from decimal import Decimal, getcontext, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP
from fractions import Fraction
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Callable,
    TypeVar,
    Generic,
    Iterator,
    Generator
)
from dataclasses import dataclass, field
from enum import Enum
import scipy.stats as stats
from scipy.optimize import minimize, minimize_scalar
from scipy.fft import fft, ifft
import pandas as pd

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
R = TypeVar('R')

# ============================================================
# CONSTANTS
# ============================================================

# Constantes mathématiques
PHI = (1 + math.sqrt(5)) / 2  # Nombre d'or
EULER = math.e
PI = math.pi
TAU = 2 * math.pi

# Précision par défaut
DEFAULT_PRECISION = 8
DEFAULT_ROUNDING = ROUND_HALF_UP

# ============================================================
# DECIMAL UTILITIES
# ============================================================

class DecimalUtils:
    """Utilitaires pour Decimal"""
    
    @staticmethod
    def to_decimal(
        value: Any,
        precision: int = DEFAULT_PRECISION
    ) -> Decimal:
        """
        Convertit en Decimal
        
        Args:
            value: Valeur à convertir
            precision: Précision
            
        Returns:
            Decimal: Valeur convertie
        """
        getcontext().prec = precision
        
        if isinstance(value, Decimal):
            return value
        elif isinstance(value, (int, float)):
            return Decimal(str(value))
        elif isinstance(value, str):
            return Decimal(value)
        else:
            return Decimal(str(value))
    
    @staticmethod
    def round_decimal(
        value: Decimal,
        precision: int = DEFAULT_PRECISION,
        rounding: str = DEFAULT_ROUNDING
    ) -> Decimal:
        """
        Arrondit un Decimal
        
        Args:
            value: Valeur à arrondir
            precision: Précision
            rounding: Méthode d'arrondi
            
        Returns:
            Decimal: Valeur arrondie
        """
        return value.quantize(Decimal('1.' + '0' * precision), rounding=rounding)
    
    @staticmethod
    def format_decimal(
        value: Decimal,
        precision: int = DEFAULT_PRECISION,
        grouping: bool = True
    ) -> str:
        """
        Formate un Decimal
        
        Args:
            value: Valeur à formater
            precision: Précision
            grouping: Utiliser les séparateurs de milliers
            
        Returns:
            str: Valeur formatée
        """
        formatted = format(value, f'.{precision}f')
        if grouping:
            parts = formatted.split('.')
            int_part = parts[0]
            formatted_int = ''
            for i, char in enumerate(reversed(int_part)):
                if i > 0 and i % 3 == 0:
                    formatted_int = ',' + formatted_int
                formatted_int = char + formatted_int
            formatted = f"{formatted_int}.{parts[1] if len(parts) > 1 else ''}"
        return formatted

# ============================================================
# STATISTICS UTILITIES
# ============================================================

class StatisticsUtils:
    """Utilitaires statistiques"""
    
    @staticmethod
    def mean(data: List[float]) -> float:
        """
        Calcule la moyenne
        
        Args:
            data: Données
            
        Returns:
            float: Moyenne
        """
        if not data:
            return 0.0
        return sum(data) / len(data)
    
    @staticmethod
    def median(data: List[float]) -> float:
        """
        Calcule la médiane
        
        Args:
            data: Données
            
        Returns:
            float: Médiane
        """
        if not data:
            return 0.0
        return statistics.median(data)
    
    @staticmethod
    def variance(data: List[float], sample: bool = True) -> float:
        """
        Calcule la variance
        
        Args:
            data: Données
            sample: Variance d'échantillon
            
        Returns:
            float: Variance
        """
        if len(data) < 2:
            return 0.0
        return statistics.variance(data) if sample else statistics.pvariance(data)
    
    @staticmethod
    def std_dev(data: List[float], sample: bool = True) -> float:
        """
        Calcule l'écart-type
        
        Args:
            data: Données
            sample: Écart-type d'échantillon
            
        Returns:
            float: Écart-type
        """
        if len(data) < 2:
            return 0.0
        return statistics.stdev(data) if sample else statistics.pstdev(data)
    
    @staticmethod
    def quantile(data: List[float], q: float) -> float:
        """
        Calcule un quantile
        
        Args:
            data: Données
            q: Quantile (0-1)
            
        Returns:
            float: Quantile
        """
        if not data:
            return 0.0
        sorted_data = sorted(data)
        pos = (len(sorted_data) - 1) * q
        floor_pos = int(math.floor(pos))
        ceil_pos = int(math.ceil(pos))
        
        if floor_pos == ceil_pos:
            return sorted_data[floor_pos]
        
        return sorted_data[floor_pos] + (sorted_data[ceil_pos] - sorted_data[floor_pos]) * (pos - floor_pos)
    
    @staticmethod
    def iqr(data: List[float]) -> float:
        """
        Calcule l'écart interquartile
        
        Args:
            data: Données
            
        Returns:
            float: IQR
        """
        q1 = StatisticsUtils.quantile(data, 0.25)
        q3 = StatisticsUtils.quantile(data, 0.75)
        return q3 - q1
    
    @staticmethod
    def correlation(x: List[float], y: List[float]) -> float:
        """
        Calcule la corrélation de Pearson
        
        Args:
            x: Données X
            y: Données Y
            
        Returns:
            float: Corrélation
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        n = len(x)
        mean_x = StatisticsUtils.mean(x)
        mean_y = StatisticsUtils.mean(y)
        
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator = math.sqrt(
            sum((x[i] - mean_x) ** 2 for i in range(n)) *
            sum((y[i] - mean_y) ** 2 for i in range(n))
        )
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    @staticmethod
    def covariance(x: List[float], y: List[float]) -> float:
        """
        Calcule la covariance
        
        Args:
            x: Données X
            y: Données Y
            
        Returns:
            float: Covariance
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        n = len(x)
        mean_x = StatisticsUtils.mean(x)
        mean_y = StatisticsUtils.mean(y)
        
        return sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / (n - 1)
    
    @staticmethod
    def z_score(data: List[float]) -> List[float]:
        """
        Calcule les z-scores
        
        Args:
            data: Données
            
        Returns:
            List[float]: Z-scores
        """
        if not data:
            return []
        
        mean = StatisticsUtils.mean(data)
        std = StatisticsUtils.std_dev(data)
        
        if std == 0:
            return [0.0] * len(data)
        
        return [(x - mean) / std for x in data]
    
    @staticmethod
    def detect_outliers(
        data: List[float],
        method: str = 'iqr',
        threshold: float = 1.5
    ) -> List[int]:
        """
        Détecte les outliers
        
        Args:
            data: Données
            method: Méthode ('iqr', 'zscore')
            threshold: Seuil
            
        Returns:
            List[int]: Indices des outliers
        """
        if len(data) < 4:
            return []
        
        outliers = []
        
        if method == 'iqr':
            q1 = StatisticsUtils.quantile(data, 0.25)
            q3 = StatisticsUtils.quantile(data, 0.75)
            iqr_val = q3 - q1
            
            lower_bound = q1 - threshold * iqr_val
            upper_bound = q3 + threshold * iqr_val
            
            for i, val in enumerate(data):
                if val < lower_bound or val > upper_bound:
                    outliers.append(i)
        
        elif method == 'zscore':
            z_scores = StatisticsUtils.z_score(data)
            for i, z in enumerate(z_scores):
                if abs(z) > threshold:
                    outliers.append(i)
        
        return outliers

# ============================================================
# FINANCIAL MATH UTILITIES
# ============================================================

class FinancialMathUtils:
    """Utilitaires mathématiques financières"""
    
    @staticmethod
    def compound_interest(
        principal: float,
        rate: float,
        periods: float,
        compounding: int = 1
    ) -> float:
        """
        Calcule l'intérêt composé
        
        Args:
            principal: Capital initial
            rate: Taux d'intérêt
            periods: Nombre de périodes
            compounding: Nombre de périodes de composition par période
            
        Returns:
            float: Montant final
        """
        return principal * (1 + rate / compounding) ** (periods * compounding)
    
    @staticmethod
    def present_value(
        future_value: float,
        rate: float,
        periods: float
    ) -> float:
        """
        Calcule la valeur actuelle
        
        Args:
            future_value: Valeur future
            rate: Taux d'intérêt
            periods: Nombre de périodes
            
        Returns:
            float: Valeur actuelle
        """
        return future_value / (1 + rate) ** periods
    
    @staticmethod
    def future_value(
        present_value: float,
        rate: float,
        periods: float
    ) -> float:
        """
        Calcule la valeur future
        
        Args:
            present_value: Valeur actuelle
            rate: Taux d'intérêt
            periods: Nombre de périodes
            
        Returns:
            float: Valeur future
        """
        return present_value * (1 + rate) ** periods
    
    @staticmethod
    def net_present_value(
        cashflows: List[float],
        rate: float
    ) -> float:
        """
        Calcule la valeur actuelle nette
        
        Args:
            cashflows: Flux de trésorerie
            rate: Taux d'intérêt
            
        Returns:
            float: VAN
        """
        npv = 0.0
        for i, cf in enumerate(cashflows):
            npv += cf / (1 + rate) ** i
        return npv
    
    @staticmethod
    def internal_rate_of_return(
        cashflows: List[float],
        guess: float = 0.1
    ) -> float:
        """
        Calcule le taux de rendement interne
        
        Args:
            cashflows: Flux de trésorerie
            guess: Estimation initiale
            
        Returns:
            float: TRI
        """
        def npv(rate):
            return sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))
        
        # Utiliser la méthode de Newton-Raphson
        rate = guess
        for _ in range(100):
            npv_val = npv(rate)
            if abs(npv_val) < 1e-6:
                return rate
            npv_derivative = sum(-i * cf / (1 + rate) ** (i + 1) for i, cf in enumerate(cashflows))
            if abs(npv_derivative) < 1e-6:
                break
            rate = rate - npv_val / npv_derivative
        
        return rate
    
    @staticmethod
    def sharpe_ratio(
        returns: List[float],
        risk_free_rate: float = 0.0
    ) -> float:
        """
        Calcule le ratio de Sharpe
        
        Args:
            returns: Rendements
            risk_free_rate: Taux sans risque
            
        Returns:
            float: Ratio de Sharpe
        """
        if not returns:
            return 0.0
        
        mean_return = StatisticsUtils.mean(returns)
        std_return = StatisticsUtils.std_dev(returns)
        
        if std_return == 0:
            return 0.0
        
        return (mean_return - risk_free_rate) / std_return
    
    @staticmethod
    def sortino_ratio(
        returns: List[float],
        risk_free_rate: float = 0.0,
        target_return: float = 0.0
    ) -> float:
        """
        Calcule le ratio de Sortino
        
        Args:
            returns: Rendements
            risk_free_rate: Taux sans risque
            target_return: Rendement cible
            
        Returns:
            float: Ratio de Sortino
        """
        if not returns:
            return 0.0
        
        mean_return = StatisticsUtils.mean(returns)
        downside_returns = [r for r in returns if r < target_return]
        
        if not downside_returns:
            return 0.0
        
        downside_deviation = StatisticsUtils.std_dev(downside_returns)
        
        if downside_deviation == 0:
            return 0.0
        
        return (mean_return - risk_free_rate) / downside_deviation
    
    @staticmethod
    def calmar_ratio(
        returns: List[float],
        max_drawdown: float
    ) -> float:
        """
        Calcule le ratio de Calmar
        
        Args:
            returns: Rendements
            max_drawdown: Drawdown maximum
            
        Returns:
            float: Ratio de Calmar
        """
        if not returns or max_drawdown == 0:
            return 0.0
        
        annual_return = StatisticsUtils.mean(returns) * 252  # 252 jours de trading
        return annual_return / max_drawdown

# ============================================================
# SIGNAL PROCESSING UTILITIES
# ============================================================

class SignalProcessingUtils:
    """Utilitaires de traitement du signal"""
    
    @staticmethod
    def moving_average(
        data: List[float],
        window: int,
        method: str = 'simple'
    ) -> List[float]:
        """
        Calcule la moyenne mobile
        
        Args:
            data: Données
            window: Taille de la fenêtre
            method: Méthode ('simple', 'exponential', 'weighted')
            
        Returns:
            List[float]: Moyenne mobile
        """
        if len(data) < window:
            return data.copy()
        
        if method == 'simple':
            result = []
            for i in range(len(data)):
                if i < window - 1:
                    result.append(data[i])
                else:
                    result.append(sum(data[i - window + 1:i + 1]) / window)
            return result
        
        elif method == 'exponential':
            alpha = 2 / (window + 1)
            result = [data[0]]
            for i in range(1, len(data)):
                result.append(alpha * data[i] + (1 - alpha) * result[-1])
            return result
        
        elif method == 'weighted':
            weights = [1 / (window - i) for i in range(window)]
            weights = [w / sum(weights) for w in weights]
            result = []
            for i in range(len(data)):
                if i < window - 1:
                    result.append(data[i])
                else:
                    result.append(sum(data[i - window + 1 + j] * weights[j] for j in range(window)))
            return result
        
        return data
    
    @staticmethod
    def exponential_smoothing(
        data: List[float],
        alpha: float
    ) -> List[float]:
        """
        Lissage exponentiel
        
        Args:
            data: Données
            alpha: Paramètre de lissage
            
        Returns:
            List[float]: Données lissées
        """
        if not data:
            return []
        
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(alpha * data[i] + (1 - alpha) * result[-1])
        
        return result
    
    @staticmethod
    def standard_deviation(
        data: List[float],
        window: int
    ) -> List[float]:
        """
        Calcule l'écart-type mobile
        
        Args:
            data: Données
            window: Taille de la fenêtre
            
        Returns:
            List[float]: Écart-type mobile
        """
        if len(data) < window:
            return [0.0] * len(data)
        
        result = []
        for i in range(len(data)):
            if i < window - 1:
                result.append(0.0)
            else:
                window_data = data[i - window + 1:i + 1]
                result.append(StatisticsUtils.std_dev(window_data))
        
        return result
    
    @staticmethod
    def bollinger_bands(
        data: List[float],
        window: int,
        num_std: float = 2.0
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Calcule les bandes de Bollinger
        
        Args:
            data: Données
            window: Taille de la fenêtre
            num_std: Nombre d'écarts-types
            
        Returns:
            Tuple[List[float], List[float], List[float]]: (moyenne, supérieure, inférieure)
        """
        ma = SignalProcessingUtils.moving_average(data, window)
        std = SignalProcessingUtils.standard_deviation(data, window)
        
        upper = [ma[i] + num_std * std[i] for i in range(len(ma))]
        lower = [ma[i] - num_std * std[i] for i in range(len(ma))]
        
        return ma, upper, lower
    
    @staticmethod
    def rsi(
        data: List[float],
        window: int = 14
    ) -> List[float]:
        """
        Calcule le RSI (Relative Strength Index)
        
        Args:
            data: Données
            window: Taille de la fenêtre
            
        Returns:
            List[float]: RSI
        """
        if len(data) < window + 1:
            return [50.0] * len(data)
        
        gains = []
        losses = []
        
        for i in range(1, len(data)):
            change = data[i] - data[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(-change)
        
        result = []
        
        # Premier RSI
        avg_gain = sum(gains[:window]) / window
        avg_loss = sum(losses[:window]) / window
        
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - (100 / (1 + rs)))
        
        # RSI suivants
        for i in range(window, len(gains)):
            avg_gain = (avg_gain * (window - 1) + gains[i]) / window
            avg_loss = (avg_loss * (window - 1) + losses[i]) / window
            
            if avg_loss == 0:
                result.append(100.0)
            else:
                rs = avg_gain / avg_loss
                result.append(100 - (100 / (1 + rs)))
        
        # Ajouter des valeurs initiales
        result = [50.0] * window + result
        
        return result

# ============================================================
# OPTIMIZATION UTILITIES
# ============================================================

class OptimizationUtils:
    """Utilitaires d'optimisation"""
    
    @staticmethod
    def gradient_descent(
        func: Callable[[List[float]], float],
        initial_guess: List[float],
        learning_rate: float = 0.01,
        max_iterations: int = 1000,
        tolerance: float = 1e-6
    ) -> Tuple[List[float], float]:
        """
        Descente de gradient
        
        Args:
            func: Fonction à minimiser
            initial_guess: Estimation initiale
            learning_rate: Taux d'apprentissage
            max_iterations: Nombre maximum d'itérations
            tolerance: Tolérance de convergence
            
        Returns:
            Tuple[List[float], float]: (Meilleure solution, Meilleure valeur)
        """
        n = len(initial_guess)
        x = initial_guess.copy()
        
        for _ in range(max_iterations):
            # Calculer le gradient numérique
            grad = []
            epsilon = 1e-8
            
            for i in range(n):
                x_plus = x.copy()
                x_plus[i] += epsilon
                x_minus = x.copy()
                x_minus[i] -= epsilon
                
                grad_i = (func(x_plus) - func(x_minus)) / (2 * epsilon)
                grad.append(grad_i)
            
            # Mettre à jour x
            x_new = [x[i] - learning_rate * grad[i] for i in range(n)]
            
            # Vérifier la convergence
            if all(abs(x_new[i] - x[i]) < tolerance for i in range(n)):
                return x_new, func(x_new)
            
            x = x_new
        
        return x, func(x)
    
    @staticmethod
    def simulated_annealing(
        func: Callable[[List[float]], float],
        initial_guess: List[float],
        temperature: float = 100.0,
        cooling_rate: float = 0.99,
        max_iterations: int = 1000,
        min_temperature: float = 0.001
    ) -> Tuple[List[float], float]:
        """
        Recuit simulé
        
        Args:
            func: Fonction à minimiser
            initial_guess: Estimation initiale
            temperature: Température initiale
            cooling_rate: Taux de refroidissement
            max_iterations: Nombre maximum d'itérations
            min_temperature: Température minimale
            
        Returns:
            Tuple[List[float], float]: (Meilleure solution, Meilleure valeur)
        """
        n = len(initial_guess)
        current = initial_guess.copy()
        current_value = func(current)
        best = current.copy()
        best_value = current_value
        
        temp = temperature
        
        for _ in range(max_iterations):
            if temp < min_temperature:
                break
            
            # Générer un voisin
            neighbor = []
            for i in range(n):
                neighbor.append(current[i] + random.uniform(-0.1, 0.1))
            
            neighbor_value = func(neighbor)
            
            # Accepter ou rejeter
            if neighbor_value < current_value:
                current = neighbor
                current_value = neighbor_value
            else:
                delta = neighbor_value - current_value
                accept_prob = math.exp(-delta / temp)
                if random.random() < accept_prob:
                    current = neighbor
                    current_value = neighbor_value
            
            # Mettre à jour la meilleure solution
            if current_value < best_value:
                best = current.copy()
                best_value = current_value
            
            # Refroidir
            temp *= cooling_rate
        
        return best, best_value

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Constantes
    'PHI',
    'EULER',
    'PI',
    'TAU',
    'DEFAULT_PRECISION',
    
    # Classes
    'DecimalUtils',
    'StatisticsUtils',
    'FinancialMathUtils',
    'SignalProcessingUtils',
    'OptimizationUtils',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Math utilities module initialized")
