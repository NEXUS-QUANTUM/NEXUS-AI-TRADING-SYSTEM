"""
NEXUS AI TRADING SYSTEM - Backtesting Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/__init__.py
Description: Module de backtesting complet pour l'évaluation et la validation
             des stratégies de trading. Intègre l'ensemble des fonctionnalités
             nécessaires à l'analyse de performance et à la robustesse.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime

# ============================================================
# EXPORTATION DES CLASSES PRINCIPALES
# ============================================================

# Backtest Engine
from trading.backtesting.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    run_backtest
)

# Data Provider
from trading.backtesting.data_provider import (
    DataProvider,
    DataSource,
    DataCache,
    get_data_provider
)

# Metrics Calculator
from trading.backtesting.metrics_calculator import (
    MetricsCalculator,
    PerformanceMetrics,
    calculate_metrics
)

# Monte Carlo Simulation
from trading.backtesting.monte_carlo import (
    MonteCarloSimulator,
    MonteCarloConfig,
    MonteCarloResult,
    run_monte_carlo
)

# Strategy Optimizer
from trading.backtesting.optimizer import (
    StrategyOptimizer,
    OptimizationConfig,
    OptimizationResult,
    ObjectiveFunction,
    optimize_strategy
)

# Report Generator
from trading.backtesting.report_generator import (
    ReportGenerator,
    ReportConfig,
    generate_backtest_report
)

# Results Analyzer
from trading.backtesting.results_analyzer import (
    ResultsAnalyzer,
    RobustnessMetrics,
    StatisticalTests,
    ComparisonResult,
    analyze_results
)

# Market Simulator
from trading.backtesting.simulator import (
    MarketSimulator,
    SimulationConfig,
    SimulationTick,
    OrderBookEntry,
    create_simulator
)

# Strategy Runner
from trading.backtesting.strategy_runner import (
    StrategyRunner,
    RunnerConfig,
    RunnerState,
    RunnerStatus,
    ExecutionMode,
    run_strategy
)

# Walk-Forward Analysis
from trading.backtesting.walk_forward import (
    WalkForwardAnalyzer,
    WalkForwardConfig,
    WalkForwardResult,
    WalkForwardWindow,
    run_walk_forward
)

# ============================================================
# VERSION ET MÉTADONNÉES
# ============================================================

__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__license__ = "Proprietary"

# ============================================================
# CONFIGURATION DU LOGGING
# ============================================================

logger = logging.getLogger(__name__)

# Configuration par défaut du logging pour le module
def setup_logging(level: str = "INFO") -> None:
    """
    Configure le logging pour le module backtesting.
    
    Args:
        level: Niveau de logging ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configurer le logger du module
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Backtesting module logging configured at {level} level")

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def get_available_strategies() -> List[str]:
    """
    Retourne la liste des stratégies disponibles.
    
    Returns:
        Liste des noms de stratégies.
    """
    from trading.strategies.factory import StrategyFactory
    return StrategyFactory.get_available_strategies()


def get_available_symbols() -> List[str]:
    """
    Retourne la liste des symboles disponibles pour le backtesting.
    
    Returns:
        Liste des symboles.
    """
    provider = get_data_provider()
    return provider.get_available_symbols()


def clear_cache() -> None:
    """
    Vide le cache des données.
    """
    provider = get_data_provider()
    provider.clear_cache()
    logger.info("Cache vidé")


def get_cache_stats() -> Dict[str, Any]:
    """
    Retourne les statistiques du cache.
    
    Returns:
        Statistiques du cache.
    """
    provider = get_data_provider()
    return provider.get_cache_stats()


# ============================================================
# FONCTIONS DE RECHERCHE RAPIDE
# ============================================================

def quick_backtest(
    symbol: str,
    strategy: str,
    start_date: Union[str, datetime],
    end_date: Union[str, datetime],
    initial_capital: float = 100000.0,
    **kwargs
) -> BacktestResult:
    """
    Exécute un backtest rapide avec configuration simplifiée.
    
    Args:
        symbol: Symbole à tester.
        strategy: Nom de la stratégie.
        start_date: Date de début.
        end_date: Date de fin.
        initial_capital: Capital initial.
        **kwargs: Paramètres supplémentaires pour la stratégie.
        
    Returns:
        Résultats du backtest.
    """
    logger.info(f"Quick backtest: {symbol} - {strategy}")
    
    # Création de la configuration
    config = BacktestConfig(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        strategy_name=strategy,
        strategy_params=kwargs
    )
    
    # Exécution
    engine = BacktestEngine(config)
    return engine.run()


def quick_metrics(
    result: BacktestResult,
    risk_free_rate: float = 0.02
) -> PerformanceMetrics:
    """
    Calcule les métriques de performance rapidement.
    
    Args:
        result: Résultats du backtest.
        risk_free_rate: Taux sans risque.
        
    Returns:
        Métriques de performance.
    """
    calculator = MetricsCalculator(risk_free_rate)
    return calculator.calculate_all_metrics(result.equity_curve, result.trades)


def quick_optimize(
    symbol: str,
    strategy: str,
    start_date: Union[str, datetime],
    end_date: Union[str, datetime],
    param_space: Dict[str, Any],
    method: str = 'random',
    n_iterations: int = 50,
    **kwargs
) -> OptimizationResult:
    """
    Exécute une optimisation rapide.
    
    Args:
        symbol: Symbole à optimiser.
        strategy: Nom de la stratégie.
        start_date: Date de début.
        end_date: Date de fin.
        param_space: Espace des paramètres.
        method: Méthode d'optimisation.
        n_iterations: Nombre d'itérations.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Résultats de l'optimisation.
    """
    logger.info(f"Quick optimization: {symbol} - {strategy}")
    
    config = OptimizationConfig(
        strategy_name=strategy,
        param_space=param_space,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        method=method,
        n_iterations=n_iterations,
        **kwargs
    )
    
    optimizer = StrategyOptimizer(config)
    return optimizer.optimize()


def quick_report(
    result: BacktestResult,
    output_dir: str = "data/quick_reports/",
    formats: List[str] = ['html', 'pdf']
) -> Dict[str, str]:
    """
    Génère un rapport rapide.
    
    Args:
        result: Résultats du backtest.
        output_dir: Répertoire de sortie.
        formats: Formats de sortie.
        
    Returns:
        Chemins des fichiers générés.
    """
    return generate_backtest_report(
        result=result,
        output_dir=output_dir,
        formats=formats
    )


def quick_compare(
    results: List[BacktestResult],
    names: Optional[List[str]] = None
) -> ComparisonResult:
    """
    Compare rapidement plusieurs stratégies.
    
    Args:
        results: Liste des résultats de backtest.
        names: Noms des stratégies.
        
    Returns:
        Résultats de la comparaison.
    """
    analyzer = ResultsAnalyzer()
    return analyzer.compare_strategies(results, names)


def quick_walk_forward(
    symbol: str,
    strategy: str,
    start_date: Union[str, datetime],
    end_date: Union[str, datetime],
    param_space: Dict[str, Any],
    in_sample_days: int = 365,
    out_of_sample_days: int = 90,
    **kwargs
) -> WalkForwardResult:
    """
    Exécute une analyse Walk-Forward rapide.
    
    Args:
        symbol: Symbole à analyser.
        strategy: Nom de la stratégie.
        start_date: Date de début.
        end_date: Date de fin.
        param_space: Espace des paramètres.
        in_sample_days: Taille de la fenêtre d'optimisation.
        out_of_sample_days: Taille de la fenêtre de validation.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Résultats de l'analyse Walk-Forward.
    """
    logger.info(f"Quick Walk-Forward: {symbol} - {strategy}")
    
    config = WalkForwardConfig(
        symbol=symbol,
        strategy_name=strategy,
        start_date=start_date,
        end_date=end_date,
        param_space=param_space,
        in_sample_days=in_sample_days,
        out_of_sample_days=out_of_sample_days,
        **kwargs
    )
    
    analyzer = WalkForwardAnalyzer(config)
    return analyzer.run()


def quick_simulation(
    symbol: str,
    initial_price: float,
    initial_capital: float = 100000.0,
    steps: int = 1000,
    **kwargs
) -> MarketSimulator:
    """
    Crée et exécute une simulation rapide.
    
    Args:
        symbol: Symbole à simuler.
        initial_price: Prix initial.
        initial_capital: Capital initial.
        steps: Nombre de pas.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Simulateur de marché avec résultats.
    """
    logger.info(f"Quick simulation: {symbol} - {steps} steps")
    
    config = SimulationConfig(
        symbol=symbol,
        initial_price=initial_price,
        initial_capital=initial_capital,
        **kwargs
    )
    
    simulator = MarketSimulator(config)
    simulator.run_simulation(steps)
    
    return simulator

# ============================================================
# CONSTANTES ET CONFIGURATIONS PRÉDÉFINIES
# ============================================================

# Timeframes supportés
SUPPORTED_TIMEFRAMES = [
    '1m', '5m', '15m', '30m',
    '1h', '4h', '6h', '12h',
    '1d', '1w', '1M'
]

# Symboles communs
COMMON_SYMBOLS = [
    'BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD',
    'AAPL', 'GOOGL', 'MSFT', 'AMZN',
    'EUR-USD', 'GBP-USD', 'USD-JPY'
]

# Stratégies prédéfinies
PREDEFINED_STRATEGIES = {
    'momentum': {
        'description': 'Stratégie de momentum avec croisement de moyennes mobiles',
        'default_params': {
            'fast_period': 10,
            'slow_period': 30,
            'signal_threshold': 0.02
        }
    },
    'mean_reversion': {
        'description': 'Stratégie de retour vers la moyenne avec Bollinger Bands',
        'default_params': {
            'bb_period': 20,
            'bb_std': 2.0,
            'entry_threshold': 1.5
        }
    },
    'breakout': {
        'description': 'Stratégie de breakout avec niveaux de support/résistance',
        'default_params': {
            'lookback_period': 50,
            'breakout_threshold': 0.02,
            'volume_threshold': 1.5
        }
    },
    'grid': {
        'description': 'Stratégie de grid trading',
        'default_params': {
            'grid_levels': 10,
            'grid_spacing': 0.01,
            'take_profit': 0.02
        }
    },
    'ai_ensemble': {
        'description': 'Ensemble de modèles AI (LSTM, Transformer, XGBoost)',
        'default_params': {
            'model_weights': [0.3, 0.4, 0.3],
            'confidence_threshold': 0.6,
            'lookback_days': 30
        }
    }
}

# ============================================================
# VALIDATION ET UTILITAIRES
# ============================================================

def validate_symbol(symbol: str) -> bool:
    """
    Valide un symbole.
    
    Args:
        symbol: Symbole à valider.
        
    Returns:
        True si le symbole est valide.
    """
    if not symbol or not isinstance(symbol, str):
        return False
    
    # Vérification du format (ex: BTC-USD, AAPL, EUR-USD)
    parts = symbol.split('-')
    if len(parts) not in [1, 2]:
        return False
    
    return len(symbol) >= 2


def validate_date(date: Union[str, datetime]) -> bool:
    """
    Valide une date.
    
    Args:
        date: Date à valider.
        
    Returns:
        True si la date est valide.
    """
    if isinstance(date, datetime):
        return True
    
    if isinstance(date, str):
        try:
            datetime.fromisoformat(date)
            return True
        except ValueError:
            return False
    
    return False


def validate_timeframe(timeframe: str) -> bool:
    """
    Valide un timeframe.
    
    Args:
        timeframe: Timeframe à valider.
        
    Returns:
        True si le timeframe est valide.
    """
    return timeframe in SUPPORTED_TIMEFRAMES


def get_default_params(strategy_name: str) -> Dict[str, Any]:
    """
    Retourne les paramètres par défaut d'une stratégie.
    
    Args:
        strategy_name: Nom de la stratégie.
        
    Returns:
        Paramètres par défaut.
    """
    if strategy_name in PREDEFINED_STRATEGIES:
        return PREDEFINED_STRATEGIES[strategy_name]['default_params']
    return {}


def get_strategy_description(strategy_name: str) -> str:
    """
    Retourne la description d'une stratégie.
    
    Args:
        strategy_name: Nom de la stratégie.
        
    Returns:
        Description de la stratégie.
    """
    if strategy_name in PREDEFINED_STRATEGIES:
        return PREDEFINED_STRATEGIES[strategy_name]['description']
    return "Stratégie personnalisée"


# ============================================================
# CLASSES DE GESTION DE PROJET
# ============================================================

class BacktestProject:
    """
    Gestionnaire de projet de backtesting.
    Permet de gérer plusieurs backtests, de les comparer
    et de générer des rapports consolidés.
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialise un projet de backtesting.
        
        Args:
            name: Nom du projet.
            description: Description du projet.
        """
        self.name = name
        self.description = description
        self.results: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        
        logger.info(f"BacktestProject créé: {name}")
    
    def add_backtest(
        self,
        symbol: str,
        strategy: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        params: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None
    ) -> BacktestResult:
        """
        Ajoute un backtest au projet.
        
        Args:
            symbol: Symbole à tester.
            strategy: Nom de la stratégie.
            start_date: Date de début.
            end_date: Date de fin.
            params: Paramètres de la stratégie.
            name: Nom du backtest.
            
        Returns:
            Résultats du backtest.
        """
        if params is None:
            params = get_default_params(strategy)
        
        result = quick_backtest(
            symbol=symbol,
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            **params
        )
        
        entry = {
            'name': name or f"{symbol}_{strategy}_{len(self.results)}",
            'symbol': symbol,
            'strategy': strategy,
            'start_date': start_date,
            'end_date': end_date,
            'params': params,
            'result': result,
            'metrics': quick_metrics(result)
        }
        
        self.results.append(entry)
        logger.info(f"Backtest ajouté: {entry['name']}")
        
        return result
    
    def compare_all(self) -> ComparisonResult:
        """
        Compare tous les backtests du projet.
        
        Returns:
            Résultats de la comparaison.
        """
        if len(self.results) < 2:
            logger.warning("Moins de 2 backtests à comparer")
            return ComparisonResult()
        
        results = [r['result'] for r in self.results]
        names = [r['name'] for r in self.results]
        
        return quick_compare(results, names)
    
    def generate_report(
        self,
        output_dir: str = "data/project_reports/",
        formats: List[str] = ['html', 'pdf']
    ) -> Dict[str, str]:
        """
        Génère un rapport consolidé du projet.
        
        Args:
            output_dir: Répertoire de sortie.
            formats: Formats de sortie.
            
        Returns:
            Chemins des fichiers générés.
        """
        import os
        import json
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Données du projet
        project_data = {
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'total_backtests': len(self.results),
            'backtests': []
        }
        
        for r in self.results:
            project_data['backtests'].append({
                'name': r['name'],
                'symbol': r['symbol'],
                'strategy': r['strategy'],
                'params': r['params'],
                'metrics': r['metrics'].to_dict()
            })
        
        # Sauvegarde JSON
        json_path = os.path.join(output_dir, f"{self.name}_project.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, default=str)
        
        # Génération de la comparaison
        if len(self.results) >= 2:
            comparison = self.compare_all()
            comp_path = os.path.join(output_dir, f"{self.name}_comparison.json")
            with open(comp_path, 'w', encoding='utf-8') as f:
                json.dump(comparison.to_dict(), f, indent=2, default=str)
        
        # Génération des rapports individuels
        reports = {}
        for r in self.results:
            rep = generate_backtest_report(
                result=r['result'],
                output_dir=os.path.join(output_dir, r['name']),
                formats=formats
            )
            reports[r['name']] = rep
        
        return {
            'project_json': json_path,
            'comparison_json': comp_path if len(self.results) >= 2 else None,
            'individual_reports': reports
        }
    
    def summary(self) -> str:
        """
        Retourne un résumé du projet.
        
        Returns:
            Résumé textuel.
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"BACKTEST PROJECT: {self.name}")
        lines.append("=" * 60)
        lines.append(f"Description: {self.description}")
        lines.append(f"Created: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Total Backtests: {len(self.results)}")
        lines.append("")
        lines.append("BACKTESTS:")
        
        for i, r in enumerate(self.results, 1):
            metrics = r['metrics']
            lines.append(f"  {i}. {r['name']}")
            lines.append(f"     Symbol: {r['symbol']} | Strategy: {r['strategy']}")
            lines.append(f"     Return: {metrics.total_return:.2%} | Sharpe: {metrics.sharpe_ratio:.3f}")
            lines.append(f"     Drawdown: {metrics.max_drawdown_pct:.2%} | Win Rate: {metrics.win_rate:.2%}")
        
        lines.append("=" * 60)
        return "\n".join(lines)

# ============================================================
# CONFIGURATION GLOBALE
# ============================================================

# Configuration par défaut
DEFAULT_CONFIG = {
    'initial_capital': 100000.0,
    'timeframe': '1h',
    'risk_free_rate': 0.02,
    'max_positions': 5,
    'max_position_size': 10000.0,
    'min_position_size': 100.0,
    'stop_loss_pct': 0.02,
    'take_profit_pct': 0.04,
    'max_drawdown_pct': 0.20,
    'risk_per_trade_pct': 0.01
}

# ============================================================
# INITIALISATION DU MODULE
# ============================================================

logger.info("=" * 60)
logger.info("NEXUS AI TRADING SYSTEM - Backtesting Module")
logger.info(f"Version: {__version__}")
logger.info(f"Copyright: {__copyright__}")
logger.info("=" * 60)
logger.info(f"Strategies disponibles: {len(get_available_strategies())}")
logger.info(f"Symboles disponibles: {len(get_available_symbols())}")
logger.info("=" * 60)

# ============================================================
# EXPORTATION COMPLÈTE
# ============================================================

__all__ = [
    # Classes principales
    'BacktestEngine',
    'BacktestConfig',
    'BacktestResult',
    'DataProvider',
    'DataSource',
    'DataCache',
    'MetricsCalculator',
    'PerformanceMetrics',
    'MonteCarloSimulator',
    'MonteCarloConfig',
    'MonteCarloResult',
    'StrategyOptimizer',
    'OptimizationConfig',
    'OptimizationResult',
    'ObjectiveFunction',
    'ReportGenerator',
    'ReportConfig',
    'ResultsAnalyzer',
    'RobustnessMetrics',
    'StatisticalTests',
    'ComparisonResult',
    'MarketSimulator',
    'SimulationConfig',
    'SimulationTick',
    'OrderBookEntry',
    'StrategyRunner',
    'RunnerConfig',
    'RunnerState',
    'RunnerStatus',
    'ExecutionMode',
    'WalkForwardAnalyzer',
    'WalkForwardConfig',
    'WalkForwardResult',
    'WalkForwardWindow',
    'BacktestProject',
    
    # Fonctions rapides
    'run_backtest',
    'calculate_metrics',
    'run_monte_carlo',
    'optimize_strategy',
    'generate_backtest_report',
    'analyze_results',
    'run_walk_forward',
    'run_strategy',
    'create_simulator',
    'quick_backtest',
    'quick_metrics',
    'quick_optimize',
    'quick_report',
    'quick_compare',
    'quick_walk_forward',
    'quick_simulation',
    
    # Utilitaires
    'get_data_provider',
    'get_available_strategies',
    'get_available_symbols',
    'clear_cache',
    'get_cache_stats',
    'validate_symbol',
    'validate_date',
    'validate_timeframe',
    'get_default_params',
    'get_strategy_description',
    'setup_logging',
    
    # Constantes
    'SUPPORTED_TIMEFRAMES',
    'COMMON_SYMBOLS',
    'PREDEFINED_STRATEGIES',
    'DEFAULT_CONFIG',
    
    # Métadonnées
    '__version__',
    '__author__',
    '__copyright__',
    '__license__'
]

# ============================================================
# FIN DU MODULE
# ============================================================
