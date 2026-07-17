"""
NEXUS AI TRADING SYSTEM - Walk Forward Analysis
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/walk_forward.py
Description: Analyse Walk-Forward pour la validation de stratégies.
             Supporte l'optimisation glissante, la validation out-of-sample,
             l'analyse de robustesse et la détection de dérive de performance.
"""

import logging
import time
import json
import itertools
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import numpy as np
import pandas as pd
from tqdm import tqdm

from trading.backtesting.backtest_engine import BacktestEngine, BacktestConfig, BacktestResult
from trading.backtesting.metrics_calculator import MetricsCalculator, PerformanceMetrics
from trading.backtesting.optimizer import StrategyOptimizer, OptimizationConfig, OptimizationResult
from trading.backtesting.results_analyzer import ResultsAnalyzer, RobustnessMetrics
from trading.strategies.factory import StrategyFactory
from shared.helpers.date_helpers import days_between, add_days
from shared.exceptions import WalkForwardError

# Configuration du logging
logger = logging.getLogger(__name__)


@dataclass
class WalkForwardConfig:
    """
    Configuration de l'analyse Walk-Forward.
    """
    # Paramètres de base
    symbol: str
    strategy_name: str
    start_date: Union[str, datetime]
    end_date: Union[str, datetime]
    
    # Paramètres de fenêtre
    in_sample_days: int = 365  # Taille de la fenêtre d'optimisation
    out_of_sample_days: int = 90  # Taille de la fenêtre de validation
    step_days: int = 30  # Pas de décalage entre les fenêtres
    
    # Paramètres d'optimisation
    param_space: Dict[str, Any]  # Espace des paramètres à optimiser
    optimization_method: str = 'random'  # Méthode d'optimisation
    n_iterations: int = 100  # Nombre d'itérations par fenêtre
    
    # Paramètres de backtest
    initial_capital: float = 100000.0
    timeframe: str = '1h'
    
    # Paramètres de risque
    max_positions: int = 5
    max_position_size: float = 10000.0
    min_position_size: float = 100.0
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_drawdown_pct: float = 0.20
    risk_per_trade_pct: float = 0.01
    
    # Paramètres de sortie
    save_results: bool = True
    output_dir: str = "data/walk_forward_results/"
    parallel: bool = True
    n_workers: int = 4
    verbose: bool = True
    
    def __post_init__(self):
        """Validation des paramètres."""
        if isinstance(self.start_date, str):
            self.start_date = datetime.fromisoformat(self.start_date)
        if isinstance(self.end_date, str):
            self.end_date = datetime.fromisoformat(self.end_date)
        
        if self.start_date >= self.end_date:
            raise WalkForwardError("La date de début doit être avant la date de fin")
        
        if self.in_sample_days <= 0:
            raise WalkForwardError("in_sample_days doit être > 0")
        
        if self.out_of_sample_days <= 0:
            raise WalkForwardError("out_of_sample_days doit être > 0")
        
        if self.step_days <= 0:
            raise WalkForwardError("step_days doit être > 0")
        
        if not self.param_space:
            raise WalkForwardError("param_space ne peut pas être vide")
        
        if self.strategy_name not in StrategyFactory.get_available_strategies():
            raise WalkForwardError(f"Stratégie '{self.strategy_name}' non trouvée")


@dataclass
class WalkForwardWindow:
    """
    Une fenêtre de l'analyse Walk-Forward.
    """
    # Dates
    in_sample_start: datetime
    in_sample_end: datetime
    out_of_sample_start: datetime
    out_of_sample_end: datetime
    
    # Résultats
    optimal_params: Dict[str, Any] = field(default_factory=dict)
    optimization_score: float = 0.0
    in_sample_performance: Dict[str, float] = field(default_factory=dict)
    out_of_sample_performance: Dict[str, float] = field(default_factory=dict)
    
    # Métadonnées
    window_index: int = 0
    optimization_time: float = 0.0
    backtest_time: float = 0.0
    trades_count: int = 0
    status: str = "pending"  # pending, running, completed, failed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'window_index': self.window_index,
            'in_sample_start': self.in_sample_start.isoformat(),
            'in_sample_end': self.in_sample_end.isoformat(),
            'out_of_sample_start': self.out_of_sample_start.isoformat(),
            'out_of_sample_end': self.out_of_sample_end.isoformat(),
            'optimal_params': self.optimal_params,
            'optimization_score': self.optimization_score,
            'in_sample_performance': self.in_sample_performance,
            'out_of_sample_performance': self.out_of_sample_performance,
            'optimization_time': self.optimization_time,
            'backtest_time': self.backtest_time,
            'trades_count': self.trades_count,
            'status': self.status
        }


@dataclass
class WalkForwardResult:
    """
    Résultats complets de l'analyse Walk-Forward.
    """
    # Configuration
    config: WalkForwardConfig = None
    
    # Fenêtres
    windows: List[WalkForwardWindow] = field(default_factory=list)
    
    # Métriques globales
    total_windows: int = 0
    successful_windows: int = 0
    failed_windows: int = 0
    
    # Performance globale
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    
    # Statistiques des paramètres
    parameter_stability: Dict[str, Dict[str, float]] = field(default_factory=dict)
    parameter_trends: Dict[str, List[float]] = field(default_factory=dict)
    
    # Performance des paramètres optimaux
    optimal_performance: Dict[str, float] = field(default_factory=dict)
    fixed_performance: Dict[str, float] = field(default_factory=dict)
    
    # Analyse de robustesse
    robustness_score: float = 0.0
    performance_decay: float = 0.0
    out_of_sample_consistency: float = 0.0
    
    # Métadonnées
    total_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'config': {
                'symbol': self.config.symbol,
                'strategy_name': self.config.strategy_name,
                'in_sample_days': self.config.in_sample_days,
                'out_of_sample_days': self.config.out_of_sample_days,
                'step_days': self.config.step_days
            },
            'total_windows': self.total_windows,
            'successful_windows': self.successful_windows,
            'failed_windows': self.failed_windows,
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'parameter_stability': self.parameter_stability,
            'robustness_score': self.robustness_score,
            'performance_decay': self.performance_decay,
            'out_of_sample_consistency': self.out_of_sample_consistency,
            'total_time': self.total_time,
            'windows': [w.to_dict() for w in self.windows]
        }
    
    def summary(self) -> str:
        """Retourne un résumé lisible."""
        lines = []
        lines.append("=" * 80)
        lines.append("WALK-FORWARD ANALYSIS RESULTS")
        lines.append("=" * 80)
        lines.append(f"Symbol:                    {self.config.symbol}")
        lines.append(f"Strategy:                  {self.config.strategy_name}")
        lines.append(f"Total Windows:             {self.total_windows}")
        lines.append(f"Successful:                {self.successful_windows}")
        lines.append(f"Failed:                    {self.failed_windows}")
        lines.append("")
        lines.append("GLOBAL PERFORMANCE:")
        lines.append(f"  Total Return:            {self.total_return:.2%}")
        lines.append(f"  Annualized Return:       {self.annualized_return:.2%}")
        lines.append(f"  Sharpe Ratio:            {self.sharpe_ratio:.3f}")
        lines.append(f"  Max Drawdown:            {self.max_drawdown:.2%}")
        lines.append(f"  Win Rate:                {self.win_rate:.2%}")
        lines.append("")
        lines.append("ROBUSTNESS:")
        lines.append(f"  Robustness Score:        {self.robustness_score:.3f}")
        lines.append(f"  Performance Decay:       {self.performance_decay:.3f}")
        lines.append(f"  OOS Consistency:         {self.out_of_sample_consistency:.3f}")
        lines.append("")
        lines.append("PARAMETER STABILITY:")
        for param, stats in self.parameter_stability.items():
            lines.append(f"  {param}: mean={stats.get('mean', 0):.3f}, "
                        f"std={stats.get('std', 0):.3f}, "
                        f"trend={stats.get('trend', 0):.3f}")
        lines.append("=" * 80)
        return "\n".join(lines)


class WalkForwardAnalyzer:
    """
    Analyse Walk-Forward pour la validation de stratégies.
    """
    
    def __init__(self, config: WalkForwardConfig):
        """
        Initialise l'analyseur Walk-Forward.
        
        Args:
            config: Configuration de l'analyse.
        """
        self.config = config
        self.results = WalkForwardResult()
        self.results.config = config
        
        # Composants
        self.metrics_calculator = MetricsCalculator()
        self.results_analyzer = ResultsAnalyzer()
        
        # Cache pour éviter de réoptimiser
        self._optimization_cache = {}
        
        logger.info("WalkForwardAnalyzer initialisé")
        logger.info(f"Stratégie: {config.strategy_name}, Symbole: {config.symbol}")
        logger.info(f"Fenêtre IS: {config.in_sample_days}j, OOS: {config.out_of_sample_days}j, Pas: {config.step_days}j")
    
    # ============================================================
    # GÉNÉRATION DES FENÊTRES
    # ============================================================
    
    def _generate_windows(self) -> List[Dict[str, datetime]]:
        """
        Génère les fenêtres de l'analyse Walk-Forward.
        
        Returns:
            Liste des fenêtres.
        """
        windows = []
        current_start = self.config.start_date
        
        window_index = 0
        while True:
            # Fenêtre in-sample
            in_sample_start = current_start
            in_sample_end = add_days(in_sample_start, self.config.in_sample_days)
            
            # Fenêtre out-of-sample
            out_of_sample_start = in_sample_end
            out_of_sample_end = add_days(out_of_sample_start, self.config.out_of_sample_days)
            
            # Vérification de la fin
            if out_of_sample_end > self.config.end_date:
                break
            
            windows.append({
                'in_sample_start': in_sample_start,
                'in_sample_end': in_sample_end,
                'out_of_sample_start': out_of_sample_start,
                'out_of_sample_end': out_of_sample_end,
                'index': window_index
            })
            
            # Avancer
            current_start = add_days(current_start, self.config.step_days)
            window_index += 1
        
        logger.info(f"Généré {len(windows)} fenêtres")
        return windows
    
    # ============================================================
    # OPTIMISATION PAR FENÊTRE
    # ============================================================
    
    def _optimize_window(
        self,
        window: Dict[str, datetime],
        window_index: int
    ) -> Tuple[Dict[str, Any], float, Dict[str, float]]:
        """
        Optimise les paramètres pour une fenêtre.
        
        Args:
            window: Fenêtre à optimiser.
            window_index: Index de la fenêtre.
            
        Returns:
            Tuple (meilleurs paramètres, score, performance).
        """
        logger.debug(f"Optimisation fenêtre {window_index}...")
        
        # Création de la configuration d'optimisation
        opt_config = OptimizationConfig(
            strategy_name=self.config.strategy_name,
            param_space=self.config.param_space,
            symbol=self.config.symbol,
            start_date=window['in_sample_start'].isoformat(),
            end_date=window['in_sample_end'].isoformat(),
            initial_capital=self.config.initial_capital,
            timeframe=self.config.timeframe,
            method=self.config.optimization_method,
            n_iterations=self.config.n_iterations,
            max_positions=self.config.max_positions,
            max_position_size=self.config.max_position_size,
            min_position_size=self.config.min_position_size,
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct,
            max_drawdown_limit=self.config.max_drawdown_pct,
            risk_per_trade_pct=self.config.risk_per_trade_pct,
            objective='sharpe_ratio',
            maximize=True,
            verbose=False,
            save_results=False
        )
        
        # Exécution de l'optimisation
        optimizer = StrategyOptimizer(opt_config)
        opt_result = optimizer.optimize()
        
        # Performance in-sample
        in_sample_perf = {}
        if opt_result.best_result:
            in_sample_perf = {
                'total_return': opt_result.best_result.total_return,
                'sharpe_ratio': opt_result.best_result.sharpe_ratio,
                'max_drawdown': opt_result.best_result.max_drawdown_pct,
                'win_rate': opt_result.best_result.win_rate,
                'profit_factor': opt_result.best_result.profit_factor
            }
        
        return (
            opt_result.best_params,
            opt_result.best_score,
            in_sample_perf
        )
    
    # ============================================================
    # BACKTEST PAR FENÊTRE
    # ============================================================
    
    def _backtest_window(
        self,
        window: Dict[str, datetime],
        params: Dict[str, Any],
        window_index: int
    ) -> Dict[str, float]:
        """
        Effectue un backtest sur la fenêtre out-of-sample.
        
        Args:
            window: Fenêtre à tester.
            params: Paramètres à utiliser.
            window_index: Index de la fenêtre.
            
        Returns:
            Performance out-of-sample.
        """
        logger.debug(f"Backtest OOS fenêtre {window_index}...")
        
        # Configuration du backtest
        backtest_config = BacktestConfig(
            symbol=self.config.symbol,
            start_date=window['out_of_sample_start'],
            end_date=window['out_of_sample_end'],
            initial_capital=self.config.initial_capital,
            timeframe=self.config.timeframe,
            strategy_name=self.config.strategy_name,
            strategy_params=params,
            max_positions=self.config.max_positions,
            max_position_size=self.config.max_position_size,
            min_position_size=self.config.min_position_size,
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct,
            max_drawdown_pct=self.config.max_drawdown_pct,
            risk_per_trade_pct=self.config.risk_per_trade_pct
        )
        
        # Exécution du backtest
        engine = BacktestEngine(backtest_config)
        result = engine.run()
        
        return {
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown_pct,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'total_trades': result.total_trades,
            'equity_curve': result.equity_curve.tolist() if hasattr(result, 'equity_curve') else []
        }
    
    # ============================================================
    # EXÉCUTION COMPLÈTE
    # ============================================================
    
    def run(self) -> WalkForwardResult:
        """
        Exécute l'analyse Walk-Forward complète.
        
        Returns:
            Résultats de l'analyse.
        """
        start_time = time.time()
        logger.info("Démarrage de l'analyse Walk-Forward...")
        
        # Génération des fenêtres
        windows = self._generate_windows()
        self.results.total_windows = len(windows)
        
        # Exécution
        if self.config.parallel and len(windows) > 1:
            self._run_parallel(windows)
        else:
            self._run_sequential(windows)
        
        # Calcul des métriques globales
        self._calculate_global_metrics()
        
        # Calcul de la robustesse
        self._calculate_robustness()
        
        # Sauvegarde
        if self.config.save_results:
            self._save_results()
        
        self.results.total_time = time.time() - start_time
        
        logger.info("Analyse Walk-Forward terminée")
        logger.info(self.results.summary())
        
        return self.results
    
    def _run_sequential(self, windows: List[Dict[str, datetime]]) -> None:
        """
        Exécute l'analyse séquentiellement.
        
        Args:
            windows: Liste des fenêtres.
        """
        with tqdm(total=len(windows), desc="Walk-Forward") as pbar:
            for window in windows:
                try:
                    self._process_window(window)
                    self.results.successful_windows += 1
                except Exception as e:
                    logger.error(f"Erreur fenêtre {window['index']}: {e}")
                    self.results.failed_windows += 1
                
                pbar.update(1)
    
    def _run_parallel(self, windows: List[Dict[str, datetime]]) -> None:
        """
        Exécute l'analyse en parallèle.
        
        Args:
            windows: Liste des fenêtres.
        """
        logger.info(f"Exécution parallèle avec {self.config.n_workers} workers...")
        
        with ProcessPoolExecutor(max_workers=self.config.n_workers) as executor:
            # Soumission des tâches
            futures = []
            for window in windows:
                future = executor.submit(self._process_window, window)
                futures.append(future)
            
            # Récupération des résultats
            with tqdm(total=len(futures), desc="Walk-Forward (parallel)") as pbar:
                for future in futures:
                    try:
                        future.result()
                        self.results.successful_windows += 1
                    except Exception as e:
                        logger.error(f"Erreur dans une tâche parallèle: {e}")
                        self.results.failed_windows += 1
                    
                    pbar.update(1)
    
    def _process_window(self, window: Dict[str, datetime]) -> WalkForwardWindow:
        """
        Traite une fenêtre complète.
        
        Args:
            window: Fenêtre à traiter.
            
        Returns:
            Résultats de la fenêtre.
        """
        window_index = window['index']
        
        wf_window = WalkForwardWindow(
            in_sample_start=window['in_sample_start'],
            in_sample_end=window['in_sample_end'],
            out_of_sample_start=window['out_of_sample_start'],
            out_of_sample_end=window['out_of_sample_end'],
            window_index=window_index
        )
        
        try:
            wf_window.status = "running"
            
            # 1. Optimisation in-sample
            opt_start = time.time()
            params, score, in_perf = self._optimize_window(window, window_index)
            wf_window.optimization_time = time.time() - opt_start
            
            wf_window.optimal_params = params
            wf_window.optimization_score = score
            wf_window.in_sample_performance = in_perf
            
            # 2. Backtest out-of-sample
            bt_start = time.time()
            out_perf = self._backtest_window(window, params, window_index)
            wf_window.backtest_time = time.time() - bt_start
            
            wf_window.out_of_sample_performance = out_perf
            wf_window.trades_count = out_perf.get('total_trades', 0)
            
            wf_window.status = "completed"
            
            logger.debug(f"Fenêtre {window_index} terminée: "
                        f"IS score={score:.4f}, OOS return={out_perf.get('total_return', 0):.2%}")
            
        except Exception as e:
            wf_window.status = "failed"
            logger.error(f"Fenêtre {window_index} échouée: {e}")
            raise
        
        # Ajout aux résultats
        self.results.windows.append(wf_window)
        
        return wf_window
    
    # ============================================================
    # ANALYSE GLOBALE
    # ============================================================
    
    def _calculate_global_metrics(self) -> None:
        """
        Calcule les métriques globales.
        """
        if not self.results.windows:
            return
        
        # Extraction des performances OOS
        oos_returns = []
        oos_sharpe = []
        oos_drawdown = []
        oos_win_rate = []
        
        for w in self.results.windows:
            if w.status == "completed":
                perf = w.out_of_sample_performance
                oos_returns.append(perf.get('total_return', 0))
                oos_sharpe.append(perf.get('sharpe_ratio', 0))
                oos_drawdown.append(perf.get('max_drawdown', 0))
                oos_win_rate.append(perf.get('win_rate', 0))
        
        if oos_returns:
            self.results.total_return = np.mean(oos_returns)
            self.results.annualized_return = self.results.total_return * (365 / self.config.out_of_sample_days)
            self.results.sharpe_ratio = np.mean(oos_sharpe)
            self.results.max_drawdown = np.mean(oos_drawdown)
            self.results.win_rate = np.mean(oos_win_rate)
        
        # Analyse de stabilité des paramètres
        param_values = defaultdict(list)
        
        for w in self.results.windows:
            if w.status == "completed":
                for param, value in w.optimal_params.items():
                    if isinstance(value, (int, float)):
                        param_values[param].append(value)
        
        for param, values in param_values.items():
            if len(values) > 1:
                self.results.parameter_stability[param] = {
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values),
                    'trend': self._calculate_trend(values)
                }
                self.results.parameter_trends[param] = values
    
    def _calculate_trend(self, values: List[float]) -> float:
        """
        Calcule la tendance d'une série de valeurs.
        
        Args:
            values: Liste des valeurs.
            
        Returns:
            Tendance (coefficient de corrélation avec l'index).
        """
        if len(values) < 2:
            return 0.0
        
        x = np.arange(len(values))
        y = np.array(values)
        
        # Coefficient de corrélation
        corr = np.corrcoef(x, y)[0, 1]
        return corr if not np.isnan(corr) else 0.0
    
    def _calculate_robustness(self) -> None:
        """
        Calcule les métriques de robustesse.
        """
        if len(self.results.windows) < 2:
            return
        
        # Récupération des performances OOS
        oos_returns = []
        for w in self.results.windows:
            if w.status == "completed":
                oos_returns.append(w.out_of_sample_performance.get('total_return', 0))
        
        if not oos_returns:
            return
        
        # 1. Robustesse (consistance des performances)
        mean_return = np.mean(oos_returns)
        std_return = np.std(oos_returns)
        
        if mean_return > 0:
            self.results.out_of_sample_consistency = 1 - (std_return / (mean_return + 0.01))
        else:
            self.results.out_of_sample_consistency = 0
        
        # 2. Décroissance de performance
        if len(oos_returns) >= 3:
            first_half = np.mean(oos_returns[:len(oos_returns)//2])
            second_half = np.mean(oos_returns[len(oos_returns)//2:])
            
            if first_half > 0:
                self.results.performance_decay = max(0, 1 - (second_half / first_half))
            else:
                self.results.performance_decay = 1
        
        # 3. Score de robustesse global
        self.results.robustness_score = (
            0.5 * self.results.out_of_sample_consistency +
            0.3 * (1 - self.results.performance_decay) +
            0.2 * (self.results.sharpe_ratio / (self.results.sharpe_ratio + 1))
        )
    
    # ============================================================
    # COMPARAISON AVEC PARAMÈTRES FIXES
    # ============================================================
    
    def compare_with_fixed_parameters(
        self,
        fixed_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare les paramètres optimisés avec des paramètres fixes.
        
        Args:
            fixed_params: Paramètres fixes à tester.
            
        Returns:
            Comparaison des performances.
        """
        logger.info("Comparaison avec paramètres fixes...")
        
        # Création de la configuration de backtest
        backtest_config = BacktestConfig(
            symbol=self.config.symbol,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            initial_capital=self.config.initial_capital,
            timeframe=self.config.timeframe,
            strategy_name=self.config.strategy_name,
            strategy_params=fixed_params,
            max_positions=self.config.max_positions,
            max_position_size=self.config.max_position_size,
            min_position_size=self.config.min_position_size,
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct,
            max_drawdown_pct=self.config.max_drawdown_pct,
            risk_per_trade_pct=self.config.risk_per_trade_pct
        )
        
        # Exécution du backtest
        engine = BacktestEngine(backtest_config)
        result = engine.run()
        
        # Métriques
        fixed_perf = {
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown_pct,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'total_trades': result.total_trades
        }
        
        # Comparaison avec les paramètres optimisés
        comparison = {
            'fixed_parameters': fixed_params,
            'fixed_performance': fixed_perf,
            'optimized_performance': {
                'total_return': self.results.total_return,
                'sharpe_ratio': self.results.sharpe_ratio,
                'max_drawdown': self.results.max_drawdown,
                'win_rate': self.results.win_rate
            },
            'improvement': {
                'total_return': self.results.total_return - fixed_perf['total_return'],
                'sharpe_ratio': self.results.sharpe_ratio - fixed_perf['sharpe_ratio'],
                'max_drawdown': fixed_perf['max_drawdown'] - self.results.max_drawdown,
                'win_rate': self.results.win_rate - fixed_perf['win_rate']
            }
        }
        
        self.results.fixed_performance = fixed_perf
        self.results.optimal_performance = {
            'total_return': self.results.total_return,
            'sharpe_ratio': self.results.sharpe_ratio,
            'max_drawdown': self.results.max_drawdown,
            'win_rate': self.results.win_rate
        }
        
        return comparison
    
    # ============================================================
    # SAUVEGARDE
    # ============================================================
    
    def _save_results(self) -> None:
        """
        Sauvegarde les résultats de l'analyse.
        """
        import os
        import json
        
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"walkforward_{self.config.symbol}_{self.config.strategy_name}_{timestamp}.json"
        filepath = os.path.join(self.config.output_dir, filename)
        
        # Exportation
        data = self.results.to_dict()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Résultats sauvegardés: {filepath}")
        
        # Sauvegarde également en CSV pour les fenêtres
        csv_filename = f"walkforward_windows_{self.config.symbol}_{self.config.strategy_name}_{timestamp}.csv"
        csv_path = os.path.join(self.config.output_dir, csv_filename)
        
        # Création du DataFrame
        rows = []
        for w in self.results.windows:
            rows.append({
                'window': w.window_index,
                'is_start': w.in_sample_start.isoformat(),
                'is_end': w.in_sample_end.isoformat(),
                'oos_start': w.out_of_sample_start.isoformat(),
                'oos_end': w.out_of_sample_end.isoformat(),
                'is_sharpe': w.in_sample_performance.get('sharpe_ratio', 0),
                'oos_return': w.out_of_sample_performance.get('total_return', 0),
                'oos_sharpe': w.out_of_sample_performance.get('sharpe_ratio', 0),
                'oos_drawdown': w.out_of_sample_performance.get('max_drawdown', 0),
                'status': w.status,
                **{f'param_{k}': v for k, v in w.optimal_params.items()}
            })
        
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(csv_path, index=False)
            logger.info(f"Données des fenêtres sauvegardées: {csv_path}")


# Fonctions utilitaires
def run_walk_forward(
    symbol: str,
    strategy_name: str,
    start_date: Union[str, datetime],
    end_date: Union[str, datetime],
    param_space: Dict[str, Any],
    in_sample_days: int = 365,
    out_of_sample_days: int = 90,
    step_days: int = 30,
    **kwargs
) -> WalkForwardResult:
    """
    Fonction utilitaire pour exécuter une analyse Walk-Forward.
    
    Args:
        symbol: Symbole à analyser.
        strategy_name: Nom de la stratégie.
        start_date: Date de début.
        end_date: Date de fin.
        param_space: Espace des paramètres.
        in_sample_days: Taille de la fenêtre d'optimisation.
        out_of_sample_days: Taille de la fenêtre de validation.
        step_days: Pas de décalage.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Résultats de l'analyse Walk-Forward.
    """
    config = WalkForwardConfig(
        symbol=symbol,
        strategy_name=strategy_name,
        start_date=start_date,
        end_date=end_date,
        param_space=param_space,
        in_sample_days=in_sample_days,
        out_of_sample_days=out_of_sample_days,
        step_days=step_days,
        **kwargs
    )
    
    analyzer = WalkForwardAnalyzer(config)
    return analyzer.run()


# Exportation
__all__ = [
    'WalkForwardAnalyzer',
    'WalkForwardConfig',
    'WalkForwardResult',
    'WalkForwardWindow',
    'run_walk_forward'
]
