"""
NEXUS AI TRADING SYSTEM - Results Analyzer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/results_analyzer.py
Description: Analyseur approfondi des résultats de backtesting.
             Supporte l'analyse de robustesse, les tests statistiques,
             l'analyse de sensibilité et la comparaison de stratégies.
"""

import logging
import math
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import (
    ttest_ind, mannwhitneyu, f_oneway, 
    shapiro, anderson, kstest, normaltest
)
from scipy.signal import find_peaks

from trading.backtesting.backtest_engine import BacktestResult
from trading.backtesting.metrics_calculator import MetricsCalculator, PerformanceMetrics
from trading.backtesting.monte_carlo import MonteCarloSimulator, MonteCarloConfig
from shared.helpers.number_helpers import round_decimal
from shared.exceptions import AnalysisError

# Configuration du logging
logger = logging.getLogger(__name__)


@dataclass
class RobustnessMetrics:
    """
    Métriques de robustesse d'une stratégie.
    """
    # Stabilité des performances
    performance_stability: float = 0.0  # Écart-type des performances glissantes
    consistency_score: float = 0.0  # Score de cohérence (0-1)
    
    # Sensibilité aux paramètres
    parameter_sensitivity: Dict[str, float] = field(default_factory=dict)
    average_sensitivity: float = 0.0
    
    # Robustesse aux conditions de marché
    bull_performance: float = 0.0
    bear_performance: float = 0.0
    sideways_performance: float = 0.0
    market_regime_consistency: float = 0.0
    
    # Robustesse temporelle
    out_of_sample_performance: float = 0.0
    rolling_performance_std: float = 0.0
    performance_decay: float = 0.0
    
    # Score global
    robustness_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'performance_stability': round(self.performance_stability, 4),
            'consistency_score': round(self.consistency_score, 4),
            'parameter_sensitivity': {k: round(v, 4) for k, v in self.parameter_sensitivity.items()},
            'average_sensitivity': round(self.average_sensitivity, 4),
            'bull_performance': round(self.bull_performance, 4),
            'bear_performance': round(self.bear_performance, 4),
            'sideways_performance': round(self.sideways_performance, 4),
            'market_regime_consistency': round(self.market_regime_consistency, 4),
            'out_of_sample_performance': round(self.out_of_sample_performance, 4),
            'rolling_performance_std': round(self.rolling_performance_std, 4),
            'performance_decay': round(self.performance_decay, 4),
            'robustness_score': round(self.robustness_score, 4)
        }


@dataclass
class StatisticalTests:
    """
    Résultats des tests statistiques.
    """
    # Tests de normalité
    shapiro_wilk: Dict[str, Any] = field(default_factory=dict)
    anderson_darling: Dict[str, Any] = field(default_factory=dict)
    kolmogorov_smirnov: Dict[str, Any] = field(default_factory=dict)
    
    # Tests de comparaison
    t_test: Dict[str, Any] = field(default_factory=dict)
    mann_whitney: Dict[str, Any] = field(default_factory=dict)
    anova: Dict[str, Any] = field(default_factory=dict)
    
    # Tests de distribution
    distribution: Dict[str, Any] = field(default_factory=dict)
    
    # Tests de corrélation
    correlation: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'shapiro_wilk': self.shapiro_wilk,
            'anderson_darling': self.anderson_darling,
            'kolmogorov_smirnov': self.kolmogorov_smirnov,
            't_test': self.t_test,
            'mann_whitney': self.mann_whitney,
            'anova': self.anova,
            'distribution': self.distribution,
            'correlation': self.correlation
        }


@dataclass
class ComparisonResult:
    """
    Résultats de comparaison entre stratégies.
    """
    # Métriques comparées
    metrics_comparison: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Classement
    ranking: List[Dict[str, Any]] = field(default_factory=list)
    
    # Tests statistiques
    statistical_tests: StatisticalTests = field(default_factory=StatisticalTests)
    
    # Analyse des corrélations
    correlation_matrix: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Score de supériorité
    superiority_score: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'metrics_comparison': self.metrics_comparison,
            'ranking': self.ranking,
            'statistical_tests': self.statistical_tests.to_dict(),
            'correlation_matrix': self.correlation_matrix.tolist() if len(self.correlation_matrix) > 0 else [],
            'superiority_score': self.superiority_score
        }


class ResultsAnalyzer:
    """
    Analyseur approfondi des résultats de backtesting.
    """
    
    def __init__(self, metrics_calculator: Optional[MetricsCalculator] = None):
        """
        Initialise l'analyseur.
        
        Args:
            metrics_calculator: Calculateur de métriques (optionnel).
        """
        self.metrics_calculator = metrics_calculator or MetricsCalculator()
        self.monte_carlo = MonteCarloSimulator()
        
        logger.info("ResultsAnalyzer initialisé")
    
    # ============================================================
    # ANALYSE DE ROBUSTESSE
    # ============================================================
    
    def analyze_robustness(
        self,
        result: BacktestResult,
        n_rolling_windows: int = 10,
        n_sensitivity_points: int = 10
    ) -> RobustnessMetrics:
        """
        Analyse la robustesse d'une stratégie.
        
        Args:
            result: Résultats du backtesting.
            n_rolling_windows: Nombre de fenêtres glissantes.
            n_sensitivity_points: Nombre de points pour l'analyse de sensibilité.
            
        Returns:
            Métriques de robustesse.
        """
        logger.info("Analyse de robustesse...")
        
        metrics = RobustnessMetrics()
        
        # 1. Stabilité des performances
        rolling_performances = self._calculate_rolling_performances(
            result, n_rolling_windows
        )
        metrics.performance_stability = np.std(rolling_performances)
        metrics.rolling_performance_std = metrics.performance_stability
        
        # 2. Cohérence (proportion de périodes positives)
        positive_periods = sum(1 for p in rolling_performances if p > 0)
        metrics.consistency_score = positive_periods / len(rolling_performances) if rolling_performances else 0
        
        # 3. Sensibilité aux paramètres
        if hasattr(result, 'config') and hasattr(result.config, 'strategy_params'):
            sensitivity = self._analyze_parameter_sensitivity(
                result, n_sensitivity_points
            )
            metrics.parameter_sensitivity = sensitivity
            metrics.average_sensitivity = np.mean(list(sensitivity.values())) if sensitivity else 0
        
        # 4. Performance par régime de marché
        regime_performances = self._analyze_market_regimes(result)
        metrics.bull_performance = regime_performances.get('bull', 0)
        metrics.bear_performance = regime_performances.get('bear', 0)
        metrics.sideways_performance = regime_performances.get('sideways', 0)
        
        # 5. Cohérence entre régimes
        regimes = [metrics.bull_performance, metrics.bear_performance, metrics.sideways_performance]
        metrics.market_regime_consistency = 1 - np.std(regimes) if regimes else 0
        
        # 6. Performance out-of-sample (si disponible)
        if hasattr(result, 'out_of_sample_performance'):
            metrics.out_of_sample_performance = result.out_of_sample_performance
        
        # 7. Décroissance de performance
        metrics.performance_decay = self._calculate_performance_decay(result)
        
        # 8. Score global de robustesse
        metrics.robustness_score = self._calculate_robustness_score(metrics)
        
        logger.info(f"Score de robustesse: {metrics.robustness_score:.3f}")
        
        return metrics
    
    def _calculate_rolling_performances(
        self,
        result: BacktestResult,
        n_windows: int
    ) -> List[float]:
        """
        Calcule les performances sur fenêtres glissantes.
        
        Args:
            result: Résultats du backtesting.
            n_windows: Nombre de fenêtres.
            
        Returns:
            Liste des performances par fenêtre.
        """
        if not hasattr(result, 'equity_curve') or result.equity_curve.empty:
            return []
        
        equity = result.equity_curve
        n = len(equity)
        
        if n < n_windows * 2:
            # Pas assez de données
            return [result.total_return]
        
        window_size = n // n_windows
        performances = []
        
        for i in range(0, n - window_size, window_size // 2):
            window_equity = equity.iloc[i:i+window_size]
            if len(window_equity) > 1:
                perf = (window_equity.iloc[-1] / window_equity.iloc[0]) - 1
                performances.append(perf)
        
        return performances if performances else [result.total_return]
    
    def _analyze_parameter_sensitivity(
        self,
        result: BacktestResult,
        n_points: int
    ) -> Dict[str, float]:
        """
        Analyse la sensibilité aux paramètres.
        
        Args:
            result: Résultats du backtesting.
            n_points: Nombre de points par paramètre.
            
        Returns:
            Sensibilité par paramètre.
        """
        sensitivity = {}
        
        if not hasattr(result, 'config') or not hasattr(result.config, 'strategy_params'):
            return sensitivity
        
        base_params = result.config.strategy_params
        base_score = result.sharpe_ratio
        
        for param_name, base_value in base_params.items():
            if not isinstance(base_value, (int, float)):
                continue
            
            # Variation du paramètre
            variations = self._generate_parameter_variations(
                base_value, n_points
            )
            
            scores = []
            for var in variations:
                params = base_params.copy()
                params[param_name] = var
                
                # Création d'une configuration de test
                test_result = self._evaluate_params(params, result.config)
                if test_result:
                    scores.append(test_result.sharpe_ratio)
            
            if scores:
                # Sensibilité = écart-type relatif
                rel_std = np.std(scores) / (abs(base_score) + 1e-6)
                sensitivity[param_name] = rel_std
        
        return sensitivity
    
    def _generate_parameter_variations(
        self,
        base_value: float,
        n_points: int
    ) -> List[float]:
        """
        Génère des variations autour d'une valeur.
        
        Args:
            base_value: Valeur de base.
            n_points: Nombre de points.
            
        Returns:
            Liste des valeurs variées.
        """
        if base_value == 0:
            range_size = 1.0
        else:
            range_size = abs(base_value) * 0.5
        
        variations = np.linspace(
            base_value - range_size,
            base_value + range_size,
            n_points
        )
        
        # S'assurer que les valeurs sont positives si la base l'est
        if base_value > 0:
            variations = np.maximum(variations, 0.01)
        
        return variations.tolist()
    
    def _evaluate_params(
        self,
        params: Dict[str, Any],
        config: Any
    ) -> Optional[BacktestResult]:
        """
        Évalue des paramètres alternatifs.
        
        Args:
            params: Paramètres à tester.
            config: Configuration de base.
            
        Returns:
            Résultats du backtest ou None.
        """
        try:
            from trading.backtesting.backtest_engine import BacktestEngine, BacktestConfig
            
            # Création de la configuration
            test_config = BacktestConfig(
                symbol=config.symbol,
                start_date=config.start_date,
                end_date=config.end_date,
                initial_capital=config.initial_capital,
                timeframe=config.timeframe,
                strategy_name=config.strategy_name,
                strategy_params=params
            )
            
            # Exécution du backtest
            engine = BacktestEngine(test_config)
            return engine.run()
            
        except Exception as e:
            logger.debug(f"Erreur lors de l'évaluation des paramètres: {e}")
            return None
    
    def _analyze_market_regimes(
        self,
        result: BacktestResult
    ) -> Dict[str, float]:
        """
        Analyse la performance par régime de marché.
        
        Args:
            result: Résultats du backtesting.
            
        Returns:
            Performances par régime.
        """
        regimes = {'bull': 0, 'bear': 0, 'sideways': 0}
        
        if not hasattr(result, 'equity_curve') or result.equity_curve.empty:
            return regimes
        
        # Calcul des tendances
        equity = result.equity_curve
        n = len(equity)
        window = max(20, n // 20)
        
        # Calcul des rendements glissants
        if n > window:
            rolling_returns = equity.pct_change(window).dropna()
            
            # Classification des régimes
            bull_mask = rolling_returns > 0.02  # 2% sur la fenêtre
            bear_mask = rolling_returns < -0.02
            sideways_mask = (rolling_returns >= -0.02) & (rolling_returns <= 0.02)
            
            # Performance par régime
            if bull_mask.any():
                bull_periods = rolling_returns[bull_mask].index
                bull_equity = equity.loc[bull_periods]
                regimes['bull'] = (bull_equity.iloc[-1] / bull_equity.iloc[0]) - 1 if len(bull_equity) > 1 else 0
            
            if bear_mask.any():
                bear_periods = rolling_returns[bear_mask].index
                bear_equity = equity.loc[bear_periods]
                regimes['bear'] = (bear_equity.iloc[-1] / bear_equity.iloc[0]) - 1 if len(bear_equity) > 1 else 0
            
            if sideways_mask.any():
                sideways_periods = rolling_returns[sideways_mask].index
                sideways_equity = equity.loc[sideways_periods]
                regimes['sideways'] = (sideways_equity.iloc[-1] / sideways_equity.iloc[0]) - 1 if len(sideways_equity) > 1 else 0
        
        return regimes
    
    def _calculate_performance_decay(
        self,
        result: BacktestResult
    ) -> float:
        """
        Calcule la décroissance de performance.
        
        Args:
            result: Résultats du backtesting.
            
        Returns:
            Décroissance (0 = aucune, 1 = maximum).
        """
        if not hasattr(result, 'equity_curve') or result.equity_curve.empty:
            return 0.0
        
        equity = result.equity_curve
        n = len(equity)
        
        if n < 50:
            return 0.0
        
        # Séparation en 2 moitiés
        half = n // 2
        first_half = equity.iloc[:half]
        second_half = equity.iloc[half:]
        
        perf_first = (first_half.iloc[-1] / first_half.iloc[0]) - 1
        perf_second = (second_half.iloc[-1] / second_half.iloc[0]) - 1
        
        if perf_first > 0:
            decay = 1 - (perf_second / perf_first) if perf_second < perf_first else 0
        else:
            decay = 0
        
        return max(0, min(1, decay))
    
    def _calculate_robustness_score(self, metrics: RobustnessMetrics) -> float:
        """
        Calcule le score global de robustesse.
        
        Args:
            metrics: Métriques de robustesse.
            
        Returns:
            Score de robustesse (0-1).
        """
        # Normalisation des métriques
        scores = []
        
        # Stabilité (moins de variance = mieux)
        stability_score = 1 / (1 + metrics.performance_stability * 10)
        scores.append(stability_score * 0.2)
        
        # Cohérence
        scores.append(metrics.consistency_score * 0.2)
        
        # Sensibilité (moins de sensibilité = mieux)
        sensitivity_score = 1 / (1 + metrics.average_sensitivity)
        scores.append(sensitivity_score * 0.15)
        
        # Cohérence entre régimes
        scores.append(metrics.market_regime_consistency * 0.2)
        
        # Décroissance (moins de décroissance = mieux)
        decay_score = 1 - metrics.performance_decay
        scores.append(decay_score * 0.15)
        
        # Performance out-of-sample
        if metrics.out_of_sample_performance > 0:
            oos_score = min(1, metrics.out_of_sample_performance * 5)
        else:
            oos_score = 0
        scores.append(oos_score * 0.1)
        
        return sum(scores)
    
    # ============================================================
    # TESTS STATISTIQUES
    # ============================================================
    
    def run_statistical_tests(
        self,
        result: BacktestResult,
        benchmark_result: Optional[BacktestResult] = None
    ) -> StatisticalTests:
        """
        Exécute des tests statistiques sur les résultats.
        
        Args:
            result: Résultats du backtesting.
            benchmark_result: Résultats de référence (optionnel).
            
        Returns:
            Résultats des tests statistiques.
        """
        logger.info("Exécution des tests statistiques...")
        
        tests = StatisticalTests()
        
        # Extraction des rendements
        returns = self._extract_returns(result)
        
        if len(returns) < 5:
            logger.warning("Pas assez de données pour les tests statistiques")
            return tests
        
        # Tests de normalité
        tests.shapiro_wilk = self._test_normality_shapiro(returns)
        tests.anderson_darling = self._test_normality_anderson(returns)
        tests.kolmogorov_smirnov = self._test_normality_kstest(returns)
        
        # Tests de distribution
        tests.distribution = self._analyze_distribution(returns)
        
        # Tests de comparaison (si benchmark disponible)
        if benchmark_result:
            benchmark_returns = self._extract_returns(benchmark_result)
            
            if len(benchmark_returns) > 5:
                tests.t_test = self._test_t_test(returns, benchmark_returns)
                tests.mann_whitney = self._test_mann_whitney(returns, benchmark_returns)
                tests.anova = self._test_anova(returns, benchmark_returns)
        
        # Tests de corrélation
        tests.correlation = self._test_correlation(returns)
        
        return tests
    
    def _extract_returns(self, result: BacktestResult) -> np.ndarray:
        """
        Extrait les rendements d'un résultat.
        
        Args:
            result: Résultats du backtesting.
            
        Returns:
            Array des rendements.
        """
        if hasattr(result, 'trades') and result.trades:
            pnls = [t.pnl for t in result.trades if hasattr(t, 'pnl')]
            if pnls:
                return np.array(pnls)
        
        # Utiliser la courbe de capitaux
        if hasattr(result, 'equity_curve') and not result.equity_curve.empty:
            equity = result.equity_curve
            returns = equity.pct_change().dropna()
            return returns.values
        
        return np.array([])
    
    def _test_normality_shapiro(self, data: np.ndarray) -> Dict[str, Any]:
        """
        Test de normalité de Shapiro-Wilk.
        
        Args:
            data: Données à tester.
            
        Returns:
            Résultats du test.
        """
        if len(data) < 3 or len(data) > 5000:
            return {'statistic': None, 'p_value': None, 'normal': None}
        
        try:
            statistic, p_value = shapiro(data)
            return {
                'statistic': statistic,
                'p_value': p_value,
                'normal': p_value > 0.05
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _test_normality_anderson(self, data: np.ndarray) -> Dict[str, Any]:
        """
        Test de normalité d'Anderson-Darling.
        
        Args:
            data: Données à tester.
            
        Returns:
            Résultats du test.
        """
        if len(data) < 4:
            return {'statistic': None, 'normal': None}
        
        try:
            result = anderson(data)
            return {
                'statistic': result.statistic,
                'critical_values': result.critical_values.tolist(),
                'significance_levels': result.significance_level.tolist(),
                'normal': result.statistic < result.critical_values[2]  # 5% niveau
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _test_normality_kstest(self, data: np.ndarray) -> Dict[str, Any]:
        """
        Test de normalité de Kolmogorov-Smirnov.
        
        Args:
            data: Données à tester.
            
        Returns:
            Résultats du test.
        """
        if len(data) < 4:
            return {'statistic': None, 'p_value': None, 'normal': None}
        
        try:
            # Normaliser les données
            data_norm = (data - np.mean(data)) / np.std(data)
            statistic, p_value = kstest(data_norm, 'norm')
            return {
                'statistic': statistic,
                'p_value': p_value,
                'normal': p_value > 0.05
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_distribution(self, data: np.ndarray) -> Dict[str, Any]:
        """
        Analyse la distribution des données.
        
        Args:
            data: Données à analyser.
            
        Returns:
            Statistiques de distribution.
        """
        if len(data) < 3:
            return {}
        
        return {
            'mean': np.mean(data),
            'median': np.median(data),
            'std': np.std(data),
            'skewness': stats.skew(data),
            'kurtosis': stats.kurtosis(data),
            'min': np.min(data),
            'max': np.max(data),
            'percentiles': {
                '25': np.percentile(data, 25),
                '50': np.percentile(data, 50),
                '75': np.percentile(data, 75),
                '90': np.percentile(data, 90),
                '95': np.percentile(data, 95),
                '99': np.percentile(data, 99)
            },
            'iqr': np.percentile(data, 75) - np.percentile(data, 25),
            'outliers': self._detect_outliers(data)
        }
    
    def _detect_outliers(self, data: np.ndarray) -> Dict[str, Any]:
        """
        Détecte les valeurs aberrantes.
        
        Args:
            data: Données à analyser.
            
        Returns:
            Statistiques des outliers.
        """
        if len(data) < 4:
            return {'count': 0, 'indices': []}
        
        # Méthode IQR
        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outlier_mask = (data < lower_bound) | (data > upper_bound)
        outlier_indices = np.where(outlier_mask)[0].tolist()
        
        return {
            'count': len(outlier_indices),
            'indices': outlier_indices[:50],  # Limiter pour l'affichage
            'lower_bound': lower_bound,
            'upper_bound': upper_bound
        }
    
    def _test_t_test(
        self,
        data1: np.ndarray,
        data2: np.ndarray
    ) -> Dict[str, Any]:
        """
        Test t de Student pour deux échantillons.
        
        Args:
            data1: Premier échantillon.
            data2: Deuxième échantillon.
            
        Returns:
            Résultats du test.
        """
        if len(data1) < 2 or len(data2) < 2:
            return {}
        
        try:
            statistic, p_value = ttest_ind(data1, data2)
            return {
                'statistic': statistic,
                'p_value': p_value,
                'significant': p_value < 0.05,
                'mean_diff': np.mean(data1) - np.mean(data2)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _test_mann_whitney(
        self,
        data1: np.ndarray,
        data2: np.ndarray
    ) -> Dict[str, Any]:
        """
        Test de Mann-Whitney U (non paramétrique).
        
        Args:
            data1: Premier échantillon.
            data2: Deuxième échantillon.
            
        Returns:
            Résultats du test.
        """
        if len(data1) < 2 or len(data2) < 2:
            return {}
        
        try:
            statistic, p_value = mannwhitneyu(data1, data2)
            return {
                'statistic': statistic,
                'p_value': p_value,
                'significant': p_value < 0.05
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _test_anova(
        self,
        data1: np.ndarray,
        data2: np.ndarray
    ) -> Dict[str, Any]:
        """
        Test ANOVA (Analyse de Variance).
        
        Args:
            data1: Premier échantillon.
            data2: Deuxième échantillon.
            
        Returns:
            Résultats du test.
        """
        if len(data1) < 3 or len(data2) < 3:
            return {}
        
        try:
            statistic, p_value = f_oneway(data1, data2)
            return {
                'statistic': statistic,
                'p_value': p_value,
                'significant': p_value < 0.05
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _test_correlation(self, data: np.ndarray) -> Dict[str, Any]:
        """
        Teste l'autocorrélation des données.
        
        Args:
            data: Données à tester.
            
        Returns:
            Résultats du test.
        """
        if len(data) < 5:
            return {}
        
        results = {}
        
        try:
            # Autocorrélation (lag 1)
            corr_lag1 = np.corrcoef(data[:-1], data[1:])[0, 1]
            results['autocorrelation_lag1'] = corr_lag1
            
            # Test de Durbin-Watson
            diff = np.diff(data)
            dw_statistic = np.sum(diff ** 2) / np.sum(data ** 2) if np.sum(data ** 2) > 0 else 0
            results['durbin_watson'] = dw_statistic
            
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    # ============================================================
    # COMPARAISON DE STRATÉGIES
    # ============================================================
    
    def compare_strategies(
        self,
        results: List[BacktestResult],
        names: Optional[List[str]] = None
    ) -> ComparisonResult:
        """
        Compare plusieurs stratégies.
        
        Args:
            results: Liste des résultats de backtest.
            names: Noms des stratégies (optionnel).
            
        Returns:
            Résultats de la comparaison.
        """
        logger.info(f"Comparaison de {len(results)} stratégies...")
        
        comparison = ComparisonResult()
        
        if names is None:
            names = [f"Strategy_{i+1}" for i in range(len(results))]
        
        if len(results) != len(names):
            raise AnalysisError("Le nombre de résultats ne correspond pas aux noms")
        
        # Métriques comparées
        metrics_keys = [
            'total_return', 'annualized_return', 'sharpe_ratio',
            'sortino_ratio', 'calmar_ratio', 'win_rate',
            'profit_factor', 'max_drawdown_pct'
        ]
        
        comparison.metrics_comparison = {}
        for name, result in zip(names, results):
            comparison.metrics_comparison[name] = {}
            metrics = self.metrics_calculator.calculate_all_metrics(
                result.equity_curve, result.trades
            )
            for key in metrics_keys:
                if hasattr(metrics, key):
                    comparison.metrics_comparison[name][key] = getattr(metrics, key)
                elif hasattr(result, key):
                    comparison.metrics_comparison[name][key] = getattr(result, key)
        
        # Classement
        comparison.ranking = self._rank_strategies(
            comparison.metrics_comparison, metrics_keys
        )
        
        # Tests statistiques
        if len(results) >= 2:
            returns_list = [self._extract_returns(r) for r in results if len(self._extract_returns(r)) > 3]
            
            if len(returns_list) >= 2:
                # Comparaison par paires
                stat_tests = StatisticalTests()
                
                for i in range(len(returns_list)):
                    for j in range(i+1, len(returns_list)):
                        if len(returns_list[i]) > 2 and len(returns_list[j]) > 2:
                            name_i = names[i] if i < len(names) else f"S{i}"
                            name_j = names[j] if j < len(names) else f"S{j}"
                            key = f"{name_i}_vs_{name_j}"
                            
                            stat_tests.t_test[key] = self._test_t_test(
                                returns_list[i], returns_list[j]
                            )
                            stat_tests.mann_whitney[key] = self._test_mann_whitney(
                                returns_list[i], returns_list[j]
                            )
                
                comparison.statistical_tests = stat_tests
        
        # Score de supériorité
        comparison.superiority_score = self._calculate_superiority_scores(
            comparison.metrics_comparison
        )
        
        # Matrice de corrélation
        if len(results) >= 2:
            returns_matrix = []
            for result in results:
                returns = self._extract_returns(result)
                if len(returns) > 0:
                    returns_matrix.append(returns[:min(len(r) for r in returns_list)])
            
            if len(returns_matrix) >= 2:
                # Pad to same length
                max_len = max(len(r) for r in returns_matrix)
                padded_matrix = []
                for r in returns_matrix:
                    if len(r) < max_len:
                        padded = np.pad(r, (0, max_len - len(r)), constant_values=np.nan)
                    else:
                        padded = r[:max_len]
                    padded_matrix.append(padded)
                
                # Correlation matrix
                valid_mask = ~np.isnan(padded_matrix).any(axis=0)
                valid_data = np.array(padded_matrix)[:, valid_mask]
                
                if valid_data.shape[1] > 1:
                    correlation_matrix = np.corrcoef(valid_data)
                    comparison.correlation_matrix = correlation_matrix
        
        return comparison
    
    def _rank_strategies(
        self,
        metrics: Dict[str, Dict[str, float]],
        keys: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Classe les stratégies selon leurs métriques.
        
        Args:
            metrics: Métriques des stratégies.
            keys: Clés à utiliser pour le classement.
            
        Returns:
            Classement des stratégies.
        """
        if not metrics:
            return []
        
        scores = {}
        
        for name, metric_dict in metrics.items():
            score = 0
            for key in keys:
                if key in metric_dict:
                    # Normalisation du score
                    value = metric_dict[key]
                    if key in ['max_drawdown_pct']:
                        # Plus bas est mieux
                        score -= value * 0.1
                    else:
                        # Plus haut est mieux
                        score += value
            
            scores[name] = score
        
        # Tri par score
        sorted_names = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        ranking = []
        for rank, (name, score) in enumerate(sorted_names, 1):
            ranking.append({
                'rank': rank,
                'name': name,
                'score': score,
                'metrics': metrics.get(name, {})
            })
        
        return ranking
    
    def _calculate_superiority_scores(
        self,
        metrics: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Calcule les scores de supériorité.
        
        Args:
            metrics: Métriques des stratégies.
            
        Returns:
            Scores de supériorité.
        """
        if not metrics:
            return {}
        
        # Trouver le meilleur pour chaque métrique
        best_values = {}
        for name, metric_dict in metrics.items():
            for key, value in metric_dict.items():
                if key not in best_values:
                    best_values[key] = value
                else:
                    if key in ['max_drawdown_pct']:
                        best_values[key] = min(best_values[key], value)
                    else:
                        best_values[key] = max(best_values[key], value)
        
        # Calcul des scores
        superiority_scores = {}
        
        for name, metric_dict in metrics.items():
            score = 0
            count = 0
            
            for key, value in metric_dict.items():
                if key in best_values:
                    if best_values[key] == value:
                        score += 1
                    elif best_values[key] != 0:
                        ratio = value / best_values[key]
                        if key in ['max_drawdown_pct']:
                            ratio = best_values[key] / value if value != 0 else 0
                        score += ratio * 0.5
                    count += 1
            
            superiority_scores[name] = score / count if count > 0 else 0
        
        return superiority_scores
    
    # ============================================================
    # ANALYSE DE SENSIBILITÉ AVANCÉE
    # ============================================================
    
    def sensitivity_analysis(
        self,
        result: BacktestResult,
        param_ranges: Dict[str, Tuple[float, float]],
        n_points: int = 10
    ) -> Dict[str, Any]:
        """
        Analyse de sensibilité avancée des paramètres.
        
        Args:
            result: Résultats du backtesting.
            param_ranges: Plages de variation des paramètres.
            n_points: Nombre de points par paramètre.
            
        Returns:
            Résultats de l'analyse de sensibilité.
        """
        logger.info("Analyse de sensibilité avancée...")
        
        analysis = {}
        
        for param_name, (min_val, max_val) in param_ranges.items():
            logger.info(f"Analyse du paramètre: {param_name}")
            
            # Génération des valeurs
            values = np.linspace(min_val, max_val, n_points)
            
            # Évaluation
            scores = []
            param_results = []
            
            for value in values:
                params = result.config.strategy_params.copy()
                params[param_name] = value
                
                test_result = self._evaluate_params(params, result.config)
                if test_result:
                    scores.append(test_result.sharpe_ratio)
                    param_results.append({
                        'value': value,
                        'sharpe': test_result.sharpe_ratio,
                        'return': test_result.total_return,
                        'drawdown': test_result.max_drawdown_pct
                    })
                else:
                    scores.append(np.nan)
                    param_results.append({
                        'value': value,
                        'sharpe': np.nan,
                        'return': np.nan,
                        'drawdown': np.nan
                    })
            
            # Analyse
            valid_scores = [s for s in scores if not np.isnan(s)]
            
            if valid_scores:
                analysis[param_name] = {
                    'optimal_value': values[np.argmax(valid_scores)] if valid_scores else None,
                    'optimal_score': max(valid_scores) if valid_scores else None,
                    'mean_score': np.mean(valid_scores),
                    'std_score': np.std(valid_scores),
                    'sensitivity': np.std(valid_scores) / (abs(np.mean(valid_scores)) + 1e-6),
                    'values': values.tolist(),
                    'scores': scores,
                    'results': param_results
                }
        
        return analysis
    
    # ============================================================
    # EXPORTATION DES RÉSULTATS
    # ============================================================
    
    def export_analysis(
        self,
        result: BacktestResult,
        output_path: str,
        include_trades: bool = True,
        include_charts: bool = True
    ) -> str:
        """
        Exporte l'analyse complète en JSON.
        
        Args:
            result: Résultats du backtesting.
            output_path: Chemin de sortie.
            include_trades: Inclure les trades.
            include_charts: Inclure les graphiques (base64).
            
        Returns:
            Chemin du fichier exporté.
        """
        logger.info(f"Exportation de l'analyse vers {output_path}")
        
        # Métriques complètes
        metrics = self.metrics_calculator.calculate_all_metrics(
            result.equity_curve,
            result.trades if include_trades else None
        )
        
        # Données d'analyse
        data = {
            'metadata': {
                'symbol': result.config.symbol if hasattr(result, 'config') else None,
                'strategy': result.config.strategy_name if hasattr(result, 'config') else None,
                'start_date': result.config.start_date.isoformat() if hasattr(result, 'config') else None,
                'end_date': result.config.end_date.isoformat() if hasattr(result, 'config') else None,
                'timestamp': datetime.now().isoformat()
            },
            'metrics': metrics.to_dict(),
            'statistics': {
                'equity_curve_stats': {
                    'length': len(result.equity_curve) if hasattr(result, 'equity_curve') else 0,
                    'min': float(result.equity_curve.min()) if hasattr(result, 'equity_curve') and not result.equity_curve.empty else None,
                    'max': float(result.equity_curve.max()) if hasattr(result, 'equity_curve') and not result.equity_curve.empty else None,
                    'mean': float(result.equity_curve.mean()) if hasattr(result, 'equity_curve') and not result.equity_curve.empty else None
                }
            },
            'trades': [t.__dict__ for t in result.trades] if include_trades and hasattr(result, 'trades') else [],
            'robustness': self.analyze_robustness(result).to_dict(),
            'statistical_tests': self.run_statistical_tests(result).to_dict()
        }
        
        # Sauvegarde
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Analyse exportée: {output_path}")
        return output_path


# Fonctions utilitaires
def analyze_results(
    result: BacktestResult,
    robust: bool = True,
    statistical: bool = True
) -> Dict[str, Any]:
    """
    Fonction utilitaire pour analyser les résultats.
    
    Args:
        result: Résultats du backtesting.
        robust: Inclure l'analyse de robustesse.
        statistical: Inclure les tests statistiques.
        
    Returns:
        Dictionnaire des analyses.
    """
    analyzer = ResultsAnalyzer()
    
    analysis = {}
    
    if robust:
        analysis['robustness'] = analyzer.analyze_robustness(result).to_dict()
    
    if statistical:
        analysis['statistical_tests'] = analyzer.run_statistical_tests(result).to_dict()
    
    return analysis


# Exportation
__all__ = [
    'ResultsAnalyzer',
    'RobustnessMetrics',
    'StatisticalTests',
    'ComparisonResult',
    'analyze_results'
]
