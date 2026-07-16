"""
NEXUS AI TRADING SYSTEM - Monte Carlo Simulation
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/monte_carlo.py
Description: Simulation Monte Carlo pour l'analyse de risque et
             l'évaluation de robustesse des stratégies de trading.
             Supporte multiples méthodes de simulation et analyses.
"""

import logging
import math
import random
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from tqdm import tqdm

from shared.helpers.number_helpers import round_decimal
from shared.helpers.date_helpers import years_between
from shared.exceptions import MonteCarloError

# Configuration du logging
logger = logging.getLogger(__name__)


@dataclass
class MonteCarloConfig:
    """
    Configuration de la simulation Monte Carlo.
    """
    # Paramètres de simulation
    n_simulations: int = 1000
    n_steps: int = 252  # 1 an de trading
    initial_capital: float = 100000.0
    
    # Paramètres de distribution
    distribution: str = 'normal'  # 'normal', 'log-normal', 'student-t', 'bootstrap'
    degrees_freedom: int = 5  # Pour Student-t
    
    # Paramètres de volatilité
    volatility_model: str = 'constant'  # 'constant', 'garch', 'stochastic'
    volatility_params: Dict[str, Any] = field(default_factory=dict)
    
    # Paramètres de corrélation (multi-actifs)
    correlation_matrix: Optional[np.ndarray] = None
    
    # Paramètres de risque
    risk_free_rate: float = 0.02
    confidence_level: float = 0.95
    
    # Paramètres de sortie
    parallel: bool = False
    n_workers: int = 4
    seed: Optional[int] = 42
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.n_simulations < 10:
            raise MonteCarloError("n_simulations doit être >= 10")
        
        if self.n_steps < 10:
            raise MonteCarloError("n_steps doit être >= 10")
        
        if self.initial_capital <= 0:
            raise MonteCarloError("initial_capital doit être > 0")
        
        if self.confidence_level <= 0 or self.confidence_level >= 1:
            raise MonteCarloError("confidence_level doit être entre 0 et 1")


@dataclass
class MonteCarloResult:
    """
    Résultats de la simulation Monte Carlo.
    """
    # Statistiques de base
    mean_final_value: float = 0.0
    median_final_value: float = 0.0
    std_final_value: float = 0.0
    min_final_value: float = 0.0
    max_final_value: float = 0.0
    
    # Intervalles de confiance
    ci_90_lower: float = 0.0
    ci_90_upper: float = 0.0
    ci_95_lower: float = 0.0
    ci_95_upper: float = 0.0
    ci_99_lower: float = 0.0
    ci_99_upper: float = 0.0
    
    # Métriques de risque
    probability_loss: float = 0.0
    expected_loss: float = 0.0
    expected_gain: float = 0.0
    value_at_risk: float = 0.0
    expected_shortfall: float = 0.0
    
    # Métriques de performance
    mean_return: float = 0.0
    median_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    # Métriques de drawdown
    max_drawdown_mean: float = 0.0
    max_drawdown_median: float = 0.0
    max_drawdown_95th: float = 0.0
    max_drawdown_pct_mean: float = 0.0
    
    # Distribution finale
    final_values: np.ndarray = field(default_factory=lambda: np.array([]))
    final_returns: np.ndarray = field(default_factory=lambda: np.array([]))
    all_paths: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Métadonnées
    config: MonteCarloConfig = None
    execution_time: float = 0.0
    n_simulations: int = 0
    n_steps: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit les résultats en dictionnaire."""
        return {
            'mean_final_value': round(self.mean_final_value, 2),
            'median_final_value': round(self.median_final_value, 2),
            'std_final_value': round(self.std_final_value, 2),
            'min_final_value': round(self.min_final_value, 2),
            'max_final_value': round(self.max_final_value, 2),
            'ci_95_lower': round(self.ci_95_lower, 2),
            'ci_95_upper': round(self.ci_95_upper, 2),
            'probability_loss': round(self.probability_loss * 100, 2),
            'expected_loss': round(self.expected_loss, 2),
            'expected_gain': round(self.expected_gain, 2),
            'value_at_risk': round(self.value_at_risk, 2),
            'expected_shortfall': round(self.expected_shortfall, 2),
            'mean_return': round(self.mean_return * 100, 2),
            'sharpe_ratio': round(self.sharpe_ratio, 4),
            'max_drawdown_pct_mean': round(self.max_drawdown_pct_mean * 100, 2),
            'n_simulations': self.n_simulations,
            'n_steps': self.n_steps
        }
    
    def summary(self) -> str:
        """Retourne un résumé lisible des résultats."""
        lines = []
        lines.append("=" * 70)
        lines.append("MONTE CARLO SIMULATION RESULTS")
        lines.append("=" * 70)
        lines.append(f"Simulations:        {self.n_simulations}")
        lines.append(f"Steps per path:      {self.n_steps}")
        lines.append("")
        lines.append("FINAL VALUES:")
        lines.append(f"  Mean:              ${self.mean_final_value:,.2f}")
        lines.append(f"  Median:            ${self.median_final_value:,.2f}")
        lines.append(f"  Std Dev:           ${self.std_final_value:,.2f}")
        lines.append(f"  95% CI:            ${self.ci_95_lower:,.2f} - ${self.ci_95_upper:,.2f}")
        lines.append("")
        lines.append("RISK METRICS:")
        lines.append(f"  Loss Probability:  {self.probability_loss:.2%}")
        lines.append(f"  Expected Loss:     ${self.expected_loss:,.2f}")
        lines.append(f"  VaR (95%):         ${self.value_at_risk:,.2f}")
        lines.append(f"  CVaR (95%):        ${self.expected_shortfall:,.2f}")
        lines.append("")
        lines.append("PERFORMANCE:")
        lines.append(f"  Mean Return:       {self.mean_return:.2%}")
        lines.append(f"  Sharpe Ratio:      {self.sharpe_ratio:.3f}")
        lines.append(f"  Max DD (mean):     {self.max_drawdown_pct_mean:.2%}")
        lines.append("=" * 70)
        return "\n".join(lines)


class MonteCarloSimulator:
    """
    Simulateur Monte Carlo pour l'analyse de stratégies de trading.
    """
    
    def __init__(self, config: Optional[MonteCarloConfig] = None):
        """
        Initialise le simulateur Monte Carlo.
        
        Args:
            config: Configuration de la simulation.
        """
        self.config = config or MonteCarloConfig()
        self._validate_config()
        
        # Paramètres de distribution
        self._distribution_params = {}
        
        # Cache pour les simulations
        self._simulation_cache = {}
        
        logger.info("MonteCarloSimulator initialisé")
        logger.info(f"Simulations: {self.config.n_simulations}, Steps: {self.config.n_steps}")
    
    def _validate_config(self) -> None:
        """Valide la configuration."""
        if self.config.n_simulations < 10:
            raise MonteCarloError("n_simulations doit être >= 10")
        
        if self.config.n_steps < 10:
            raise MonteCarloError("n_steps doit être >= 10")
        
        if self.config.initial_capital <= 0:
            raise MonteCarloError("initial_capital doit être > 0")
    
    # ============================================================
    # SIMULATION DE MOUVEMENT BROWNIEN
    # ============================================================
    
    def simulate_geometric_brownian_motion(
        self,
        mu: float,
        sigma: float,
        initial_price: Optional[float] = None,
        n_simulations: Optional[int] = None,
        n_steps: Optional[int] = None
    ) -> np.ndarray:
        """
        Simule un mouvement brownien géométrique.
        
        Args:
            mu: Drift (rendement moyen annualisé).
            sigma: Volatilité annualisée.
            initial_price: Prix initial (None = utiliser initial_capital).
            n_simulations: Nombre de simulations (None = utiliser config).
            n_steps: Nombre de pas (None = utiliser config).
            
        Returns:
            Matrice de dimensions (n_simulations, n_steps+1) des prix simulés.
        """
        n_sim = n_simulations or self.config.n_simulations
        n_stp = n_steps or self.config.n_steps
        
        if initial_price is None:
            initial_price = self.config.initial_capital
        
        if self.config.seed is not None:
            np.random.seed(self.config.seed)
        
        # Paramètres du GBM
        dt = 1 / 252  # Pas de temps journalier
        mu_dt = (mu - 0.5 * sigma ** 2) * dt
        sigma_dt = sigma * np.sqrt(dt)
        
        # Simulation des rendements
        returns = np.random.normal(
            mu_dt,
            sigma_dt,
            size=(n_sim, n_stp)
        )
        
        # Calcul des prix
        log_returns = np.cumsum(returns, axis=1)
        prices = initial_price * np.exp(log_returns)
        
        # Ajout du prix initial
        prices = np.concatenate([
            np.full((n_sim, 1), initial_price),
            prices
        ], axis=1)
        
        return prices
    
    def simulate_ornstein_uhlenbeck(
        self,
        theta: float,
        mu: float,
        sigma: float,
        initial_price: Optional[float] = None,
        n_simulations: Optional[int] = None,
        n_steps: Optional[int] = None
    ) -> np.ndarray:
        """
        Simule un processus d'Ornstein-Uhlenbeck (retour vers la moyenne).
        
        Args:
            theta: Vitesse de retour vers la moyenne.
            mu: Moyenne à long terme.
            sigma: Volatilité.
            initial_price: Prix initial.
            n_simulations: Nombre de simulations.
            n_steps: Nombre de pas.
            
        Returns:
            Matrice des prix simulés.
        """
        n_sim = n_simulations or self.config.n_simulations
        n_stp = n_steps or self.config.n_steps
        
        if initial_price is None:
            initial_price = self.config.initial_capital
        
        if self.config.seed is not None:
            np.random.seed(self.config.seed)
        
        dt = 1 / 252
        prices = np.zeros((n_sim, n_stp + 1))
        prices[:, 0] = initial_price
        
        for t in range(1, n_stp + 1):
            z = np.random.normal(0, 1, n_sim)
            prices[:, t] = (
                prices[:, t-1] +
                theta * (mu - prices[:, t-1]) * dt +
                sigma * np.sqrt(dt) * z
            )
        
        return prices
    
    def simulate_merton_jump_diffusion(
        self,
        mu: float,
        sigma: float,
        lambda_jump: float,
        jump_mean: float,
        jump_std: float,
        initial_price: Optional[float] = None,
        n_simulations: Optional[int] = None,
        n_steps: Optional[int] = None
    ) -> np.ndarray:
        """
        Simule un processus de diffusion avec sauts (Merton).
        
        Args:
            mu: Drift.
            sigma: Volatilité.
            lambda_jump: Intensité des sauts.
            jump_mean: Moyenne des sauts.
            jump_std: Écart-type des sauts.
            initial_price: Prix initial.
            n_simulations: Nombre de simulations.
            n_steps: Nombre de pas.
            
        Returns:
            Matrice des prix simulés.
        """
        n_sim = n_simulations or self.config.n_simulations
        n_stp = n_steps or self.config.n_steps
        
        if initial_price is None:
            initial_price = self.config.initial_capital
        
        if self.config.seed is not None:
            np.random.seed(self.config.seed)
        
        dt = 1 / 252
        
        # Composante diffuse
        mu_dt = (mu - 0.5 * sigma ** 2) * dt
        sigma_dt = sigma * np.sqrt(dt)
        
        # Simulation
        prices = np.zeros((n_sim, n_stp + 1))
        prices[:, 0] = initial_price
        
        for t in range(1, n_stp + 1):
            # Diffusion
            z = np.random.normal(0, 1, n_sim)
            diffusive = mu_dt + sigma_dt * z
            
            # Sauts
            n_jumps = np.random.poisson(lambda_jump * dt, n_sim)
            jump = np.zeros(n_sim)
            for i in range(n_sim):
                if n_jumps[i] > 0:
                    jump[i] = np.random.normal(
                        jump_mean * n_jumps[i],
                        jump_std * np.sqrt(n_jumps[i])
                    )
            
            # Prix
            prices[:, t] = prices[:, t-1] * np.exp(diffusive + jump)
        
        return prices
    
    # ============================================================
    # SIMULATION BOOTSTRAP
    # ============================================================
    
    def simulate_bootstrap(
        self,
        historical_returns: Union[pd.Series, List[float]],
        initial_price: Optional[float] = None,
        n_simulations: Optional[int] = None,
        n_steps: Optional[int] = None,
        block_size: Optional[int] = None
    ) -> np.ndarray:
        """
        Simule en utilisant la méthode bootstrap (rééchantillonnage).
        
        Args:
            historical_returns: Rendements historiques.
            initial_price: Prix initial.
            n_simulations: Nombre de simulations.
            n_steps: Nombre de pas.
            block_size: Taille des blocs pour bootstrap par blocs.
            
        Returns:
            Matrice des prix simulés.
        """
        n_sim = n_simulations or self.config.n_simulations
        n_stp = n_steps or self.config.n_steps
        
        if initial_price is None:
            initial_price = self.config.initial_capital
        
        if self.config.seed is not None:
            np.random.seed(self.config.seed)
        
        if isinstance(historical_returns, list):
            historical_returns = pd.Series(historical_returns)
        
        historical_returns = np.array(historical_returns)
        n_historical = len(historical_returns)
        
        if n_historical == 0:
            raise MonteCarloError("Aucun rendement historique")
        
        # Simulation
        prices = np.zeros((n_sim, n_stp + 1))
        prices[:, 0] = initial_price
        
        if block_size and block_size > 1:
            # Bootstrap par blocs
            n_blocks = (n_stp + block_size - 1) // block_size
            
            for i in range(n_sim):
                returns = []
                for _ in range(n_blocks):
                    start = np.random.randint(0, n_historical - block_size + 1)
                    block = historical_returns[start:start + block_size]
                    returns.extend(block)
                
                returns = returns[:n_stp]
                log_returns = np.cumsum(returns)
                prices[i, 1:] = initial_price * np.exp(log_returns)
        else:
            # Bootstrap simple
            for i in range(n_sim):
                indices = np.random.randint(0, n_historical, n_stp)
                returns = historical_returns[indices]
                log_returns = np.cumsum(returns)
                prices[i, 1:] = initial_price * np.exp(log_returns)
        
        return prices
    
    # ============================================================
    # ANALYSE DES RÉSULTATS
    # ============================================================
    
    def analyze_results(
        self,
        paths: np.ndarray,
        initial_price: Optional[float] = None
    ) -> MonteCarloResult:
        """
        Analyse les résultats d'une simulation.
        
        Args:
            paths: Matrice des chemins simulés (n_simulations, n_steps+1).
            initial_price: Prix initial (pour le calcul des métriques).
            
        Returns:
            Objet MonteCarloResult contenant toutes les métriques.
        """
        if len(paths.shape) != 2:
            raise MonteCarloError("paths doit être une matrice 2D")
        
        n_sim, n_stp = paths.shape
        n_stp = n_stp - 1  # Nombre de pas (sans le point initial)
        
        if initial_price is None:
            initial_price = paths[:, 0].mean()
        
        result = MonteCarloResult()
        result.config = self.config
        result.n_simulations = n_sim
        result.n_steps = n_stp
        result.all_paths = paths
        
        # Valeurs finales
        final_values = paths[:, -1]
        result.final_values = final_values
        
        # Statistiques de base
        result.mean_final_value = np.mean(final_values)
        result.median_final_value = np.median(final_values)
        result.std_final_value = np.std(final_values)
        result.min_final_value = np.min(final_values)
        result.max_final_value = np.max(final_values)
        
        # Intervalles de confiance
        result.ci_90_lower = np.percentile(final_values, 5)
        result.ci_90_upper = np.percentile(final_values, 95)
        result.ci_95_lower = np.percentile(final_values, 2.5)
        result.ci_95_upper = np.percentile(final_values, 97.5)
        result.ci_99_lower = np.percentile(final_values, 0.5)
        result.ci_99_upper = np.percentile(final_values, 99.5)
        
        # Rendements
        final_returns = (final_values - initial_price) / initial_price
        result.final_returns = final_returns
        
        result.mean_return = np.mean(final_returns)
        result.median_return = np.median(final_returns)
        
        # Métriques de risque
        result.probability_loss = np.mean(final_returns < 0)
        result.expected_loss = np.mean(final_values[final_returns < 0]) if any(final_returns < 0) else 0.0
        result.expected_gain = np.mean(final_values[final_returns > 0]) if any(final_returns > 0) else 0.0
        
        # VaR et CVaR
        result.value_at_risk = initial_price - np.percentile(final_values, (1 - self.config.confidence_level) * 100)
        tail_losses = final_values[final_values < np.percentile(final_values, (1 - self.config.confidence_level) * 100)]
        result.expected_shortfall = initial_price - np.mean(tail_losses) if len(tail_losses) > 0 else 0.0
        
        # Sharpe et Sortino
        returns_series = pd.Series(
            (paths[:, t] / paths[:, t-1] - 1) for t in range(1, n_stp + 1)
        )
        # Calcul des ratios
        result.sharpe_ratio = self._calculate_sharpe_ratio(returns_series)
        result.sortino_ratio = self._calculate_sortino_ratio(returns_series)
        
        # Drawdowns
        drawdowns = self._calculate_drawdowns(paths)
        result.max_drawdown_mean = np.mean(drawdowns) if len(drawdowns) > 0 else 0.0
        result.max_drawdown_median = np.median(drawdowns) if len(drawdowns) > 0 else 0.0
        result.max_drawdown_95th = np.percentile(drawdowns, 95) if len(drawdowns) > 0 else 0.0
        result.max_drawdown_pct_mean = np.mean(drawdowns / initial_price) if len(drawdowns) > 0 else 0.0
        
        return result
    
    def _calculate_sharpe_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: Optional[float] = None
    ) -> float:
        """Calcule le ratio de Sharpe moyen."""
        if risk_free_rate is None:
            risk_free_rate = self.config.risk_free_rate
        
        mean_return = returns.mean()
        std_return = returns.std()
        
        if std_return == 0:
            return 0.0
        
        return (mean_return - risk_free_rate / 252) / std_return
    
    def _calculate_sortino_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: Optional[float] = None,
        target_return: float = 0.0
    ) -> float:
        """Calcule le ratio de Sortino moyen."""
        if risk_free_rate is None:
            risk_free_rate = self.config.risk_free_rate
        
        mean_return = returns.mean()
        downside_returns = returns[returns < target_return]
        
        if len(downside_returns) == 0:
            return float('inf')
        
        downside_std = np.sqrt(np.mean(downside_returns ** 2))
        
        if downside_std == 0:
            return 0.0
        
        return (mean_return - risk_free_rate / 252) / downside_std
    
    def _calculate_drawdowns(
        self,
        paths: np.ndarray
    ) -> np.ndarray:
        """Calcule les drawdowns maximum pour chaque chemin."""
        n_sim = paths.shape[0]
        drawdowns = np.zeros(n_sim)
        
        for i in range(n_sim):
            path = paths[i, :]
            running_max = np.maximum.accumulate(path)
            drawdown = running_max - path
            drawdowns[i] = np.max(drawdown)
        
        return drawdowns
    
    # ============================================================
    # SIMULATIONS SPÉCIALISÉES
    # ============================================================
    
    def simulate_strategy_performance(
        self,
        strategy_returns: Union[pd.Series, List[float]],
        initial_capital: Optional[float] = None,
        n_simulations: Optional[int] = None,
        n_steps: Optional[int] = None
    ) -> MonteCarloResult:
        """
        Simule la performance d'une stratégie à partir de ses rendements.
        
        Args:
            strategy_returns: Rendements de la stratégie.
            initial_capital: Capital initial.
            n_simulations: Nombre de simulations.
            n_steps: Nombre de pas.
            
        Returns:
            Résultats de la simulation.
        """
        if initial_capital is None:
            initial_capital = self.config.initial_capital
        
        n_sim = n_simulations or self.config.n_simulations
        n_stp = n_steps or self.config.n_steps
        
        if isinstance(strategy_returns, list):
            strategy_returns = pd.Series(strategy_returns)
        
        # Paramètres de la stratégie
        mean_return = strategy_returns.mean()
        std_return = strategy_returns.std()
        skewness = strategy_returns.skew() if len(strategy_returns) > 2 else 0
        kurtosis = strategy_returns.kurtosis() if len(strategy_returns) > 3 else 0
        
        logger.info(f"Stratégie - Mean: {mean_return:.4f}, Std: {std_return:.4f}")
        logger.info(f"Skewness: {skewness:.4f}, Kurtosis: {kurtosis:.4f}")
        
        # Simulation avec distribution normale ou Student-t
        if abs(kurtosis) > 1 and abs(skewness) > 0.5:
            # Distribution de Student-t (queues épaisses)
            df = 4 + 6 / (kurtosis + 3)  # Approximation
            returns = np.random.standard_t(df, (n_sim, n_stp)) * std_return + mean_return
        else:
            # Distribution normale
            returns = np.random.normal(mean_return, std_return, (n_sim, n_stp))
        
        # Calcul des prix
        log_returns = np.cumsum(returns, axis=1)
        paths = initial_capital * np.exp(log_returns)
        paths = np.concatenate([
            np.full((n_sim, 1), initial_capital),
            paths
        ], axis=1)
        
        # Analyse
        return self.analyze_results(paths, initial_capital)
    
    def simulate_portfolio(
        self,
        weights: np.ndarray,
        mean_returns: np.ndarray,
        cov_matrix: np.ndarray,
        initial_capital: Optional[float] = None,
        n_simulations: Optional[int] = None,
        n_steps: Optional[int] = None
    ) -> MonteCarloResult:
        """
        Simule la performance d'un portefeuille multi-actifs.
        
        Args:
            weights: Pondérations des actifs.
            mean_returns: Rendements moyens des actifs.
            cov_matrix: Matrice de covariance.
            initial_capital: Capital initial.
            n_simulations: Nombre de simulations.
            n_steps: Nombre de pas.
            
        Returns:
            Résultats de la simulation.
        """
        n_assets = len(weights)
        n_sim = n_simulations or self.config.n_simulations
        n_stp = n_steps or self.config.n_steps
        
        if initial_capital is None:
            initial_capital = self.config.initial_capital
        
        if self.config.seed is not None:
            np.random.seed(self.config.seed)
        
        # Simulation des rendements des actifs
        L = np.linalg.cholesky(cov_matrix)
        dt = 1 / 252
        
        returns = np.zeros((n_sim, n_stp, n_assets))
        
        for t in range(n_stp):
            z = np.random.normal(0, 1, (n_sim, n_assets))
            returns[:, t, :] = mean_returns * dt + (L @ z.T).T * np.sqrt(dt)
        
        # Rendements du portefeuille
        portfolio_returns = np.einsum('ijk,k->ij', returns, weights)
        
        # Prix du portefeuille
        log_returns = np.cumsum(portfolio_returns, axis=1)
        paths = initial_capital * np.exp(log_returns)
        paths = np.concatenate([
            np.full((n_sim, 1), initial_capital),
            paths
        ], axis=1)
        
        return self.analyze_results(paths, initial_capital)
    
    # ============================================================
    # ANALYSE DE SENSIBILITÉ
    # ============================================================
    
    def sensitivity_analysis(
        self,
        base_params: Dict[str, float],
        param_ranges: Dict[str, Tuple[float, float]],
        n_points: int = 10,
        n_simulations: Optional[int] = None,
        n_steps: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Effectue une analyse de sensibilité sur les paramètres.
        
        Args:
            base_params: Paramètres de base.
            param_ranges: Plages de variation des paramètres.
            n_points: Nombre de points par paramètre.
            n_simulations: Nombre de simulations par point.
            n_steps: Nombre de pas.
            
        Returns:
            Résultats de l'analyse de sensibilité.
        """
        n_sim = n_simulations or self.config.n_simulations
        n_stp = n_steps or self.config.n_steps
        
        results = {}
        
        for param_name, (min_val, max_val) in param_ranges.items():
            param_values = np.linspace(min_val, max_val, n_points)
            sensitivities = []
            
            for value in tqdm(param_values, desc=f"Analyse {param_name}"):
                # Création des paramètres modifiés
                params = base_params.copy()
                params[param_name] = value
                
                # Simulation
                mu = params.get('mu', 0.05)
                sigma = params.get('sigma', 0.2)
                paths = self.simulate_geometric_brownian_motion(
                    mu, sigma, n_simulations=n_sim//10, n_steps=n_stp
                )
                
                # Analyse
                result = self.analyze_results(paths)
                sensitivities.append({
                    'value': value,
                    'mean_final': result.mean_final_value,
                    'std_final': result.std_final_value,
                    'probability_loss': result.probability_loss
                })
            
            results[param_name] = pd.DataFrame(sensitivities)
        
        return results
    
    # ============================================================
    # VISUALISATION
    # ============================================================
    
    def plot_results(
        self,
        result: MonteCarloResult,
        show_paths: bool = True,
        show_distribution: bool = True,
        confidence_bands: bool = True
    ) -> None:
        """
        Visualise les résultats de la simulation.
        
        Args:
            result: Résultats de la simulation.
            show_paths: Afficher tous les chemins.
            show_distribution: Afficher la distribution.
            confidence_bands: Afficher les bandes de confiance.
        """
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
        except ImportError:
            logger.warning("Matplotlib ou Seaborn non installé")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. Tous les chemins
        if show_paths and result.all_paths is not None:
            ax = axes[0, 0]
            n_paths = min(100, result.all_paths.shape[0])
            for i in range(n_paths):
                ax.plot(result.all_paths[i, :], alpha=0.3, linewidth=0.5)
            
            # Bandes de confiance
            if confidence_bands:
                lower_95 = np.percentile(result.all_paths, 2.5, axis=0)
                upper_95 = np.percentile(result.all_paths, 97.5, axis=0)
                lower_50 = np.percentile(result.all_paths, 25, axis=0)
                upper_50 = np.percentile(result.all_paths, 75, axis=0)
                median = np.percentile(result.all_paths, 50, axis=0)
                
                ax.fill_between(range(len(lower_95)), lower_95, upper_95, alpha=0.2, color='blue')
                ax.fill_between(range(len(lower_50)), lower_50, upper_50, alpha=0.3, color='blue')
                ax.plot(median, 'b-', linewidth=2, label='Median')
            
            ax.set_xlabel('Steps')
            ax.set_ylabel('Portfolio Value')
            ax.set_title('Simulation Paths')
            ax.legend()
        
        # 2. Distribution finale
        if show_distribution:
            ax = axes[0, 1]
            sns.histplot(result.final_values, kde=True, ax=ax)
            ax.axvline(result.ci_95_lower, color='r', linestyle='--', label='95% CI')
            ax.axvline(result.ci_95_upper, color='r', linestyle='--')
            ax.axvline(result.mean_final_value, color='g', linestyle='-', label='Mean')
            ax.axvline(result.median_final_value, color='orange', linestyle='-', label='Median')
            ax.set_xlabel('Final Value')
            ax.set_ylabel('Frequency')
            ax.set_title('Distribution of Final Values')
            ax.legend()
        
        # 3. Drawdown
        ax = axes[1, 0]
        drawdowns = result.max_drawdown_mean * np.ones(10)  # Exemple
        ax.hist(drawdowns, bins=30)
        ax.set_xlabel('Max Drawdown')
        ax.set_ylabel('Frequency')
        ax.set_title('Distribution of Max Drawdowns')
        
        # 4. Métriques de risque
        ax = axes[1, 1]
        metrics = [
            ('VaR 95%', result.value_at_risk),
            ('CVaR 95%', result.expected_shortfall),
            ('Expected Loss', abs(result.expected_loss) if result.expected_loss < 0 else 0),
            ('Probability Loss', result.probability_loss)
        ]
        names, values = zip(*metrics)
        ax.bar(names, values)
        ax.set_ylabel('Value')
        ax.set_title('Risk Metrics')
        ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.show()


# Fonctions utilitaires
def run_monte_carlo(
    strategy_returns: Union[pd.Series, List[float]],
    initial_capital: float = 100000.0,
    n_simulations: int = 1000,
    n_steps: int = 252,
    **kwargs
) -> MonteCarloResult:
    """
    Fonction utilitaire pour exécuter une simulation Monte Carlo.
    
    Args:
        strategy_returns: Rendements de la stratégie.
        initial_capital: Capital initial.
        n_simulations: Nombre de simulations.
        n_steps: Nombre de pas.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Résultats de la simulation.
    """
    config = MonteCarloConfig(
        n_simulations=n_simulations,
        n_steps=n_steps,
        initial_capital=initial_capital,
        **kwargs
    )
    
    simulator = MonteCarloSimulator(config)
    return simulator.simulate_strategy_performance(strategy_returns)


# Exportation
__all__ = [
    'MonteCarloSimulator',
    'MonteCarloConfig',
    'MonteCarloResult',
    'run_monte_carlo'
]
