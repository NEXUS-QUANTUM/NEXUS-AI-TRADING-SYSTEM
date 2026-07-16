"""
NEXUS AI TRADING SYSTEM - Metrics Calculator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/metrics_calculator.py
Description: Calculateur de métriques de performance pour l'évaluation
             des stratégies de trading. Supporte les métriques standard
             et avancées (Sharpe, Sortino, Calmar, etc.)
"""

import logging
import math
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

from shared.helpers.number_helpers import round_decimal
from shared.helpers.date_helpers import days_between, years_between
from shared.exceptions import MetricsError

# Configuration du logging
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """
    Ensemble complet des métriques de performance.
    """
    # Métriques de rendement
    total_return: float = 0.0
    annualized_return: float = 0.0
    monthly_return: float = 0.0
    daily_return: float = 0.0
    
    # Métriques de risque
    volatility: float = 0.0
    annualized_volatility: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration: int = 0
    avg_drawdown: float = 0.0
    avg_drawdown_duration: int = 0
    
    # Métriques de performance ajustées au risque
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    sterling_ratio: float = 0.0
    burke_ratio: float = 0.0
    omega_ratio: float = 0.0
    tail_ratio: float = 0.0
    
    # Métriques de gestion de capital
    value_at_risk: float = 0.0
    expected_shortfall: float = 0.0
    worst_case_loss: float = 0.0
    best_case_gain: float = 0.0
    
    # Métriques de trading
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    recovery_factor: float = 0.0
    
    # Métriques de distribution
    skewness: float = 0.0
    kurtosis: float = 0.0
    
    # Métriques de performance par période
    returns: pd.Series = field(default_factory=pd.Series)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    drawdown_curve: pd.Series = field(default_factory=pd.Series)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit les métriques en dictionnaire."""
        return {
            'total_return': round(self.total_return, 4),
            'annualized_return': round(self.annualized_return, 4),
            'volatility': round(self.volatility, 4),
            'annualized_volatility': round(self.annualized_volatility, 4),
            'sharpe_ratio': round(self.sharpe_ratio, 4),
            'sortino_ratio': round(self.sortino_ratio, 4),
            'calmar_ratio': round(self.calmar_ratio, 4),
            'max_drawdown': round(self.max_drawdown, 4),
            'max_drawdown_pct': round(self.max_drawdown_pct * 100, 2),
            'max_drawdown_duration': self.max_drawdown_duration,
            'win_rate': round(self.win_rate * 100, 2),
            'profit_factor': round(self.profit_factor, 4),
            'expectancy': round(self.expectancy, 4),
            'total_trades': self.total_trades,
            'value_at_risk': round(self.value_at_risk, 4),
            'expected_shortfall': round(self.expected_shortfall, 4),
            'skewness': round(self.skewness, 4),
            'kurtosis': round(self.kurtosis, 4)
        }
    
    def to_series(self) -> pd.Series:
        """Convertit les métriques en Series pandas."""
        return pd.Series(self.to_dict())
    
    def __str__(self) -> str:
        """Représentation lisible des métriques."""
        lines = []
        lines.append("=" * 60)
        lines.append("PERFORMANCE METRICS")
        lines.append("=" * 60)
        lines.append(f"Total Return:              {self.total_return:.2%}")
        lines.append(f"Annualized Return:         {self.annualized_return:.2%}")
        lines.append(f"Volatility:                {self.volatility:.2%}")
        lines.append(f"Sharpe Ratio:              {self.sharpe_ratio:.3f}")
        lines.append(f"Sortino Ratio:             {self.sortino_ratio:.3f}")
        lines.append(f"Calmar Ratio:              {self.calmar_ratio:.3f}")
        lines.append(f"Max Drawdown:              {self.max_drawdown_pct:.2%}")
        lines.append(f"Win Rate:                  {self.win_rate:.2%}")
        lines.append(f"Profit Factor:             {self.profit_factor:.3f}")
        lines.append(f"Total Trades:              {self.total_trades}")
        lines.append("=" * 60)
        return "\n".join(lines)


class MetricsCalculator:
    """
    Calculateur de métriques de performance pour le trading.
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialise le calculateur.
        
        Args:
            risk_free_rate: Taux sans risque annuel (ex: 2% = 0.02)
        """
        self.risk_free_rate = risk_free_rate
        self.risk_free_rate_daily = (1 + risk_free_rate) ** (1/252) - 1
        
        logger.info("MetricsCalculator initialisé")
        logger.info(f"Taux sans risque: {risk_free_rate:.2%}")
    
    # ============================================================
    # MÉTRIQUES DE RENDEMENT
    # ============================================================
    
    def calculate_total_return(
        self,
        equity_curve: Union[pd.Series, List[float]]
    ) -> float:
        """
        Calcule le rendement total.
        
        Args:
            equity_curve: Courbe de capitaux.
            
        Returns:
            Rendement total (en pourcentage).
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < 2:
            return 0.0
        
        return (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
    
    def calculate_annualized_return(
        self,
        equity_curve: Union[pd.Series, List[float]],
        periods: Optional[int] = None
    ) -> float:
        """
        Calcule le rendement annualisé.
        
        Args:
            equity_curve: Courbe de capitaux.
            periods: Nombre de périodes (détecté automatiquement si None).
            
        Returns:
            Rendement annualisé (en pourcentage).
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < 2:
            return 0.0
        
        total_return = self.calculate_total_return(equity_curve)
        
        if periods is None:
            periods = len(equity_curve)
        
        years = periods / 252  # 252 jours de trading par an
        
        if years <= 0:
            return 0.0
        
        return (1 + total_return) ** (1 / years) - 1
    
    def calculate_returns(
        self,
        equity_curve: Union[pd.Series, List[float]]
    ) -> pd.Series:
        """
        Calcule les rendements périodiques.
        
        Args:
            equity_curve: Courbe de capitaux.
            
        Returns:
            Series des rendements.
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < 2:
            return pd.Series()
        
        returns = equity_curve.pct_change().dropna()
        return returns
    
    def calculate_log_returns(
        self,
        equity_curve: Union[pd.Series, List[float]]
    ) -> pd.Series:
        """
        Calcule les rendements logarithmiques.
        
        Args:
            equity_curve: Courbe de capitaux.
            
        Returns:
            Series des rendements logarithmiques.
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < 2:
            return pd.Series()
        
        log_returns = np.log(equity_curve / equity_curve.shift(1)).dropna()
        return log_returns
    
    def calculate_rolling_returns(
        self,
        equity_curve: Union[pd.Series, List[float]],
        window: int = 20
    ) -> pd.Series:
        """
        Calcule les rendements glissants.
        
        Args:
            equity_curve: Courbe de capitaux.
            window: Fenêtre de calcul.
            
        Returns:
            Series des rendements glissants.
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < window + 1:
            return pd.Series()
        
        rolling_returns = equity_curve.pct_change(periods=window).dropna()
        return rolling_returns
    
    # ============================================================
    # MÉTRIQUES DE RISQUE
    # ============================================================
    
    def calculate_volatility(
        self,
        returns: Union[pd.Series, List[float]],
        periods: Optional[int] = None
    ) -> float:
        """
        Calcule la volatilité.
        
        Args:
            returns: Rendements périodiques.
            periods: Nombre de périodes pour l'annualisation.
            
        Returns:
            Volatilité annualisée.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 2:
            return 0.0
        
        if periods is None:
            periods = len(returns)
        
        # Volatilité des rendements
        daily_vol = returns.std()
        
        # Annualisation
        years = periods / 252
        annualized_vol = daily_vol * np.sqrt(252)
        
        return annualized_vol
    
    def calculate_max_drawdown(
        self,
        equity_curve: Union[pd.Series, List[float]]
    ) -> Tuple[float, float]:
        """
        Calcule le drawdown maximum.
        
        Args:
            equity_curve: Courbe de capitaux.
            
        Returns:
            Tuple (drawdown_max_en_valeur, drawdown_max_en_pourcentage).
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < 2:
            return 0.0, 0.0
        
        # Calcul du drawdown
        running_max = equity_curve.expanding().max()
        drawdown = running_max - equity_curve
        drawdown_pct = drawdown / running_max
        
        max_drawdown = drawdown.max()
        max_drawdown_pct = drawdown_pct.max()
        
        return max_drawdown, max_drawdown_pct
    
    def calculate_drawdown_curve(
        self,
        equity_curve: Union[pd.Series, List[float]]
    ) -> pd.Series:
        """
        Calcule la courbe de drawdown.
        
        Args:
            equity_curve: Courbe de capitaux.
            
        Returns:
            Series des drawdowns.
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < 2:
            return pd.Series()
        
        running_max = equity_curve.expanding().max()
        drawdown_pct = (equity_curve - running_max) / running_max
        
        return drawdown_pct
    
    def calculate_drawdown_duration(
        self,
        equity_curve: Union[pd.Series, List[float]]
    ) -> Dict[str, Any]:
        """
        Calcule la durée des drawdowns.
        
        Args:
            equity_curve: Courbe de capitaux.
            
        Returns:
            Statistiques des durées de drawdown.
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < 2:
            return {"max": 0, "avg": 0, "current": 0}
        
        # Calcul du drawdown
        running_max = equity_curve.expanding().max()
        in_drawdown = equity_curve < running_max
        
        if not in_drawdown.any():
            return {"max": 0, "avg": 0, "current": 0}
        
        # Durée des périodes de drawdown
        drawdown_groups = (~in_drawdown).cumsum()
        drawdown_groups = drawdown_groups[in_drawdown]
        
        durations = drawdown_groups.value_counts()
        
        max_duration = durations.max() if not durations.empty else 0
        avg_duration = durations.mean() if not durations.empty else 0
        
        # Durée actuelle
        current_duration = 0
        if in_drawdown.iloc[-1]:
            current_duration = in_drawdown.iloc[::-1].cumsum().iloc[0]
        
        return {
            "max": max_duration,
            "avg": avg_duration,
            "current": current_duration
        }
    
    def calculate_value_at_risk(
        self,
        returns: Union[pd.Series, List[float]],
        confidence_level: float = 0.95,
        method: str = 'historical'
    ) -> float:
        """
        Calcule la Value at Risk (VaR).
        
        Args:
            returns: Rendements périodiques.
            confidence_level: Niveau de confiance (0.95 = 95%).
            method: Méthode ('historical', 'parametric', 'monte_carlo').
            
        Returns:
            Value at Risk.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 2:
            return 0.0
        
        if method == 'historical':
            # VaR historique
            return -np.percentile(returns, (1 - confidence_level) * 100)
        
        elif method == 'parametric':
            # VaR paramétrique (distribution normale)
            mu = returns.mean()
            sigma = returns.std()
            z_score = stats.norm.ppf(1 - confidence_level)
            return -(mu + z_score * sigma)
        
        elif method == 'monte_carlo':
            # VaR par simulation Monte Carlo
            mu = returns.mean()
            sigma = returns.std()
            n_simulations = 10000
            simulations = np.random.normal(mu, sigma, n_simulations)
            return -np.percentile(simulations, (1 - confidence_level) * 100)
        
        else:
            raise MetricsError(f"Méthode inconnue: {method}")
    
    def calculate_expected_shortfall(
        self,
        returns: Union[pd.Series, List[float]],
        confidence_level: float = 0.95
    ) -> float:
        """
        Calcule l'Expected Shortfall (CVaR).
        
        Args:
            returns: Rendements périodiques.
            confidence_level: Niveau de confiance.
            
        Returns:
            Expected Shortfall.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 2:
            return 0.0
        
        var = self.calculate_value_at_risk(returns, confidence_level)
        returns_below_var = returns[returns < -var]
        
        if returns_below_var.empty:
            return var
        
        return -returns_below_var.mean()
    
    # ============================================================
    # MÉTRIQUES AJUSTÉES AU RISQUE
    # ============================================================
    
    def calculate_sharpe_ratio(
        self,
        returns: Union[pd.Series, List[float]],
        periods: Optional[int] = None,
        risk_free_rate: Optional[float] = None
    ) -> float:
        """
        Calcule le ratio de Sharpe.
        
        Args:
            returns: Rendements périodiques.
            periods: Nombre de périodes.
            risk_free_rate: Taux sans risque (None = utiliser celui de l'instance).
            
        Returns:
            Ratio de Sharpe.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 2:
            return 0.0
        
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate
        
        if periods is None:
            periods = len(returns)
        
        # Annualisation
        years = periods / 252
        rfr_annual = risk_free_rate
        
        # Rendement annualisé
        total_return = (1 + returns.mean()) ** 252 - 1
        
        # Volatilité annualisée
        volatility = returns.std() * np.sqrt(252)
        
        if volatility == 0:
            return 0.0
        
        return (total_return - rfr_annual) / volatility
    
    def calculate_sortino_ratio(
        self,
        returns: Union[pd.Series, List[float]],
        periods: Optional[int] = None,
        risk_free_rate: Optional[float] = None,
        target_return: float = 0.0
    ) -> float:
        """
        Calcule le ratio de Sortino.
        
        Args:
            returns: Rendements périodiques.
            periods: Nombre de périodes.
            risk_free_rate: Taux sans risque.
            target_return: Rendement cible.
            
        Returns:
            Ratio de Sortino.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 2:
            return 0.0
        
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate
        
        # Calcul du rendement annualisé
        mean_return = returns.mean()
        total_return = (1 + mean_return) ** 252 - 1
        
        # Calcul du downside deviation
        downside_returns = returns[returns < target_return]
        if len(downside_returns) == 0:
            return float('inf')
        
        downside_deviation = np.sqrt(
            ((downside_returns - target_return) ** 2).sum() / len(returns)
        ) * np.sqrt(252)
        
        if downside_deviation == 0:
            return 0.0
        
        return (total_return - risk_free_rate) / downside_deviation
    
    def calculate_calmar_ratio(
        self,
        equity_curve: Union[pd.Series, List[float]],
        periods: Optional[int] = None
    ) -> float:
        """
        Calcule le ratio de Calmar.
        
        Args:
            equity_curve: Courbe de capitaux.
            periods: Nombre de périodes.
            
        Returns:
            Ratio de Calmar.
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < 2:
            return 0.0
        
        # Rendement annualisé
        annualized_return = self.calculate_annualized_return(equity_curve, periods)
        
        # Drawdown maximum
        _, max_drawdown_pct = self.calculate_max_drawdown(equity_curve)
        
        if max_drawdown_pct == 0:
            return 0.0
        
        return annualized_return / max_drawdown_pct
    
    def calculate_sterling_ratio(
        self,
        equity_curve: Union[pd.Series, List[float]],
        periods: Optional[int] = None
    ) -> float:
        """
        Calcule le ratio de Sterling.
        
        Args:
            equity_curve: Courbe de capitaux.
            periods: Nombre de périodes.
            
        Returns:
            Ratio de Sterling.
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if len(equity_curve) < 2:
            return 0.0
        
        # Rendement annualisé
        annualized_return = self.calculate_annualized_return(equity_curve, periods)
        
        # Drawdown moyen des 3 plus grands drawdowns
        drawdown_curve = self.calculate_drawdown_curve(equity_curve)
        top_drawdowns = abs(drawdown_curve).sort_values(ascending=False).head(3)
        avg_top_drawdown = top_drawdowns.mean() if len(top_drawdowns) > 0 else 0
        
        if avg_top_drawdown == 0:
            return 0.0
        
        return annualized_return / avg_top_drawdown
    
    def calculate_omega_ratio(
        self,
        returns: Union[pd.Series, List[float]],
        threshold: float = 0.0
    ) -> float:
        """
        Calcule le ratio d'Omega.
        
        Args:
            returns: Rendements périodiques.
            threshold: Seuil de rendement minimum.
            
        Returns:
            Ratio d'Omega.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 2:
            return 0.0
        
        returns_above = returns[returns > threshold]
        returns_below = returns[returns <= threshold]
        
        gains = sum(returns_above - threshold)
        losses = sum(threshold - returns_below)
        
        if losses == 0:
            return float('inf')
        
        return gains / losses
    
    def calculate_tail_ratio(
        self,
        returns: Union[pd.Series, List[float]],
        tail_size: float = 0.1
    ) -> float:
        """
        Calcule le tail ratio (ratio des queues de distribution).
        
        Args:
            returns: Rendements périodiques.
            tail_size: Taille des queues (ex: 0.1 = 10%).
            
        Returns:
            Tail ratio.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 2:
            return 0.0
        
        sorted_returns = returns.sort_values()
        
        n = len(sorted_returns)
        tail_n = max(1, int(n * tail_size))
        
        right_tail = sorted_returns.iloc[-tail_n:]
        left_tail = sorted_returns.iloc[:tail_n]
        
        if left_tail.mean() == 0:
            return 0.0
        
        return right_tail.mean() / abs(left_tail.mean())
    
    # ============================================================
    # MÉTRIQUES DE TRADING
    # ============================================================
    
    def calculate_win_rate(
        self,
        trades: List[Dict[str, Any]]
    ) -> float:
        """
        Calcule le taux de réussite.
        
        Args:
            trades: Liste des trades (doivent contenir 'pnl').
            
        Returns:
            Taux de réussite (0-1).
        """
        if not trades:
            return 0.0
        
        winning = sum(1 for t in trades if t.get('pnl', 0) > 0)
        return winning / len(trades)
    
    def calculate_profit_factor(
        self,
        trades: List[Dict[str, Any]]
    ) -> float:
        """
        Calcule le profit factor (gains / pertes).
        
        Args:
            trades: Liste des trades.
            
        Returns:
            Profit factor.
        """
        if not trades:
            return 0.0
        
        total_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        total_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
        
        if total_loss == 0:
            return float('inf') if total_profit > 0 else 0.0
        
        return total_profit / total_loss
    
    def calculate_expectancy(
        self,
        trades: List[Dict[str, Any]]
    ) -> float:
        """
        Calcule l'espérance de gain par trade.
        
        Args:
            trades: Liste des trades.
            
        Returns:
            Espérance.
        """
        if not trades:
            return 0.0
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        return total_pnl / len(trades)
    
    def calculate_recovery_factor(
        self,
        total_return: float,
        max_drawdown: float
    ) -> float:
        """
        Calcule le facteur de récupération.
        
        Args:
            total_return: Rendement total.
            max_drawdown: Drawdown maximum.
            
        Returns:
            Facteur de récupération.
        """
        if max_drawdown == 0:
            return 0.0
        
        return total_return / max_drawdown
    
    def calculate_avg_win_loss(
        self,
        trades: List[Dict[str, Any]]
    ) -> Tuple[float, float]:
        """
        Calcule le gain moyen et la perte moyenne.
        
        Args:
            trades: Liste des trades.
            
        Returns:
            Tuple (avg_win, avg_loss).
        """
        if not trades:
            return 0.0, 0.0
        
        wins = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0]
        losses = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        
        return avg_win, avg_loss
    
    # ============================================================
    # MÉTRIQUES DE DISTRIBUTION
    # ============================================================
    
    def calculate_skewness(
        self,
        returns: Union[pd.Series, List[float]]
    ) -> float:
        """
        Calcule l'asymétrie de la distribution.
        
        Args:
            returns: Rendements périodiques.
            
        Returns:
            Skewness.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 3:
            return 0.0
        
        return stats.skew(returns)
    
    def calculate_kurtosis(
        self,
        returns: Union[pd.Series, List[float]]
    ) -> float:
        """
        Calcule l'aplatissement de la distribution.
        
        Args:
            returns: Rendements périodiques.
            
        Returns:
            Kurtosis.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 4:
            return 0.0
        
        return stats.kurtosis(returns)
    
    def calculate_jarque_bera_test(
        self,
        returns: Union[pd.Series, List[float]]
    ) -> Tuple[float, float]:
        """
        Effectue le test de Jarque-Bera (normalité).
        
        Args:
            returns: Rendements périodiques.
            
        Returns:
            Tuple (statistique, p-value).
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < 4:
            return 0.0, 1.0
        
        return stats.jarque_bera(returns)
    
    # ============================================================
    # MÉTRIQUES DE PERFORMANCE PAR PÉRIODE
    # ============================================================
    
    def calculate_rolling_sharpe(
        self,
        returns: Union[pd.Series, List[float]],
        window: int = 20
    ) -> pd.Series:
        """
        Calcule le ratio de Sharpe glissant.
        
        Args:
            returns: Rendements périodiques.
            window: Fenêtre de calcul.
            
        Returns:
            Series des Sharpe ratios.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < window + 1:
            return pd.Series()
        
        rolling_sharpe = pd.Series(index=returns.index, dtype=float)
        
        for i in range(window, len(returns)):
            window_returns = returns.iloc[i-window:i]
            rolling_sharpe.iloc[i] = self.calculate_sharpe_ratio(
                window_returns, window
            )
        
        return rolling_sharpe.dropna()
    
    def calculate_rolling_volatility(
        self,
        returns: Union[pd.Series, List[float]],
        window: int = 20
    ) -> pd.Series:
        """
        Calcule la volatilité glissante.
        
        Args:
            returns: Rendements périodiques.
            window: Fenêtre de calcul.
            
        Returns:
            Series des volatilités.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if len(returns) < window + 1:
            return pd.Series()
        
        rolling_vol = returns.rolling(window=window).std() * np.sqrt(252)
        return rolling_vol.dropna()
    
    # ============================================================
    # MÉTRIQUES DE RISQUE DE QUEUE
    # ============================================================
    
    def calculate_conditional_var(
        self,
        returns: Union[pd.Series, List[float]],
        confidence_level: float = 0.95
    ) -> float:
        """
        Calcule le Conditional Value at Risk (CVaR).
        
        Args:
            returns: Rendements périodiques.
            confidence_level: Niveau de confiance.
            
        Returns:
            CVaR.
        """
        return self.calculate_expected_shortfall(returns, confidence_level)
    
    def calculate_max_loss(
        self,
        returns: Union[pd.Series, List[float]]
    ) -> float:
        """
        Calcule la perte maximale.
        
        Args:
            returns: Rendements périodiques.
            
        Returns:
            Perte maximale.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if returns.empty:
            return 0.0
        
        return returns.min()
    
    def calculate_max_gain(
        self,
        returns: Union[pd.Series, List[float]]
    ) -> float:
        """
        Calcule le gain maximum.
        
        Args:
            returns: Rendements périodiques.
            
        Returns:
            Gain maximum.
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)
        
        if returns.empty:
            return 0.0
        
        return returns.max()
    
    # ============================================================
    # MÉTRIQUES DE PERFORMANCE COMPLÈTES
    # ============================================================
    
    def calculate_all_metrics(
        self,
        equity_curve: Union[pd.Series, List[float]],
        trades: Optional[List[Dict[str, Any]]] = None,
        risk_free_rate: Optional[float] = None
    ) -> PerformanceMetrics:
        """
        Calcule toutes les métriques de performance.
        
        Args:
            equity_curve: Courbe de capitaux.
            trades: Liste des trades (optionnel).
            risk_free_rate: Taux sans risque (optionnel).
            
        Returns:
            Objet PerformanceMetrics contenant toutes les métriques.
        """
        if isinstance(equity_curve, list):
            equity_curve = pd.Series(equity_curve)
        
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate
        
        metrics = PerformanceMetrics()
        
        # Copie des données
        metrics.equity_curve = equity_curve
        
        # Métriques de rendement
        metrics.total_return = self.calculate_total_return(equity_curve)
        metrics.annualized_return = self.calculate_annualized_return(equity_curve)
        
        # Rendements
        returns = self.calculate_returns(equity_curve)
        metrics.returns = returns
        
        if not returns.empty:
            metrics.monthly_return = returns.mean() * 21  # 21 jours de trading
            metrics.daily_return = returns.mean()
        
        # Métriques de risque
        metrics.volatility = self.calculate_volatility(returns)
        metrics.annualized_volatility = metrics.volatility
        
        max_dd, max_dd_pct = self.calculate_max_drawdown(equity_curve)
        metrics.max_drawdown = max_dd
        metrics.max_drawdown_pct = max_dd_pct
        
        dd_stats = self.calculate_drawdown_duration(equity_curve)
        metrics.max_drawdown_duration = dd_stats.get('max', 0)
        
        drawdown_curve = self.calculate_drawdown_curve(equity_curve)
        metrics.drawdown_curve = drawdown_curve
        metrics.avg_drawdown = abs(drawdown_curve.mean()) if not drawdown_curve.empty else 0
        metrics.avg_drawdown_duration = dd_stats.get('avg', 0)
        
        # Métriques ajustées au risque
        metrics.sharpe_ratio = self.calculate_sharpe_ratio(returns, risk_free_rate=risk_free_rate)
        metrics.sortino_ratio = self.calculate_sortino_ratio(returns, risk_free_rate=risk_free_rate)
        metrics.calmar_ratio = self.calculate_calmar_ratio(equity_curve)
        metrics.sterling_ratio = self.calculate_sterling_ratio(equity_curve)
        
        if not returns.empty:
            metrics.omega_ratio = self.calculate_omega_ratio(returns)
            metrics.tail_ratio = self.calculate_tail_ratio(returns)
        
        # Métriques de gestion de capital
        if not returns.empty:
            metrics.value_at_risk = self.calculate_value_at_risk(returns)
            metrics.expected_shortfall = self.calculate_expected_shortfall(returns)
            metrics.worst_case_loss = self.calculate_max_loss(returns)
            metrics.best_case_gain = self.calculate_max_gain(returns)
        
        # Métriques de trading
        if trades:
            metrics.total_trades = len(trades)
            metrics.winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
            metrics.losing_trades = sum(1 for t in trades if t.get('pnl', 0) < 0)
            metrics.win_rate = self.calculate_win_rate(trades)
            metrics.profit_factor = self.calculate_profit_factor(trades)
            metrics.expectancy = self.calculate_expectancy(trades)
            metrics.recovery_factor = self.calculate_recovery_factor(
                metrics.total_return, metrics.max_drawdown
            )
            metrics.avg_win, metrics.avg_loss = self.calculate_avg_win_loss(trades)
        
        # Métriques de distribution
        if not returns.empty:
            metrics.skewness = self.calculate_skewness(returns)
            metrics.kurtosis = self.calculate_kurtosis(returns)
        
        return metrics


# Fonctions utilitaires
def calculate_metrics(
    equity_curve: Union[pd.Series, List[float]],
    trades: Optional[List[Dict[str, Any]]] = None,
    risk_free_rate: float = 0.02
) -> PerformanceMetrics:
    """
    Fonction utilitaire pour calculer les métriques de performance.
    
    Args:
        equity_curve: Courbe de capitaux.
        trades: Liste des trades (optionnel).
        risk_free_rate: Taux sans risque.
        
    Returns:
        Objet PerformanceMetrics.
    """
    calculator = MetricsCalculator(risk_free_rate)
    return calculator.calculate_all_metrics(equity_curve, trades)


# Exportation
__all__ = [
    'MetricsCalculator',
    'PerformanceMetrics',
    'calculate_metrics'
]
