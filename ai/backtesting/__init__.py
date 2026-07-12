"""
NEXUS AI TRADING SYSTEM - Backtesting Package
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Backtesting system with:
- Backtest Engine
- Data Provider
- Metrics Calculator
- Monte Carlo Simulator
- Optimizer
- Report Generator
- Results Analyzer
- Strategy Runner
- Walk-Forward Analysis
- Risk Management
- Performance Analytics
- Visualization
- Export capabilities
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type

# ========================================
# VERSION
# ========================================

__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# ========================================
# BACKTEST ENGINE
# ========================================

from ai.backtesting.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    BacktestProgress,
    BacktestStatus,
    BacktestType,
    BacktestMode,
    OptimizationMethod,
    get_backtest_engine,
    reset_backtest_engine
)

# ========================================
# DATA PROVIDER
# ========================================

from ai.backtesting.data_provider import (
    DataProvider,
    DataProviderConfig,
    DataSource,
    DataType,
    Timeframe,
    DataPoint,
    DataResponse,
    BaseDataSource,
    YahooDataSource,
    BinanceDataSource,
    get_data_provider,
    reset_data_provider
)

# ========================================
# METRICS CALCULATOR
# ========================================

from ai.backtesting.metrics_calculator import (
    MetricsCalculator,
    MetricsConfig,
    MetricType,
    AnnualizationMethod,
    PerformanceMetrics,
    RiskMetrics,
    TradeMetrics,
    PortfolioMetrics,
    RollingMetrics,
    get_metrics_calculator,
    reset_metrics_calculator
)

# ========================================
# MONTE CARLO SIMULATOR
# ========================================

from ai.backtesting.monte_carlo import (
    MonteCarloSimulator,
    MonteCarloConfig,
    SimulationMethod,
    DistributionType,
    MonteCarloResult,
    MonteCarloStats,
    get_monte_carlo,
    reset_monte_carlo
)

# ========================================
# OPTIMIZER
# ========================================

from ai.backtesting.optimizer import (
    Optimizer,
    OptimizerConfig,
    OptimizationMethod as OptimizerMethod,
    ObjectiveType,
    ParameterType,
    Parameter,
    OptimizationResult,
    OptimizationProgress,
    get_optimizer,
    reset_optimizer
)

# ========================================
# REPORT GENERATOR
# ========================================

from ai.backtesting.report_generator import (
    ReportGenerator,
    ReportConfig,
    Report,
    ReportFormat,
    ReportType,
    get_report_generator,
    reset_report_generator
)

# ========================================
# RESULTS ANALYZER
# ========================================

from ai.backtesting.results_analyzer import (
    ResultsAnalyzer,
    AnalysisConfig,
    AnalysisResult,
    AnalysisType,
    get_results_analyzer,
    reset_results_analyzer
)

# ========================================
# STRATEGY RUNNER
# ========================================

from ai.backtesting.strategy_runner import (
    StrategyRunner,
    BaseStrategy,
    TrendFollowingStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    StrategyType,
    OrderSide,
    OrderType,
    OrderStatus,
    Order,
    Position,
    Trade,
    StrategyResult,
    get_strategy_runner,
    reset_strategy_runner
)

# ========================================
# WALK-FORWARD ANALYSIS
# ========================================

from ai.backtesting.walk_forward import (
    WalkForwardAnalyzer,
    WalkForwardConfig,
    WalkForwardResult,
    WalkForwardSummary,
    WindowType,
    get_walk_forward,
    reset_walk_forward
)

# ========================================
# REGISTRIES
# ========================================

BACKTEST_COMPONENTS = {
    'engine': BacktestEngine,
    'data_provider': DataProvider,
    'metrics_calculator': MetricsCalculator,
    'monte_carlo': MonteCarloSimulator,
    'optimizer': Optimizer,
    'report_generator': ReportGenerator,
    'results_analyzer': ResultsAnalyzer,
    'strategy_runner': StrategyRunner,
    'walk_forward': WalkForwardAnalyzer
}

# ========================================
# CONFIGURATION SCHEMAS
# ========================================

BACKTEST_CONFIG_SCHEMAS = {
    'backtest': BacktestConfig,
    'data_provider': DataProviderConfig,
    'metrics': MetricsConfig,
    'monte_carlo': MonteCarloConfig,
    'optimizer': OptimizerConfig,
    'report': ReportConfig,
    'analysis': AnalysisConfig,
    'walk_forward': WalkForwardConfig
}

# ========================================
# EXPORTS
# ========================================

__all__ = [
    # Backtest Engine
    'BacktestEngine',
    'BacktestConfig',
    'BacktestResult',
    'BacktestProgress',
    'BacktestStatus',
    'BacktestType',
    'BacktestMode',
    'OptimizationMethod',
    'get_backtest_engine',
    'reset_backtest_engine',
    
    # Data Provider
    'DataProvider',
    'DataProviderConfig',
    'DataSource',
    'DataType',
    'Timeframe',
    'DataPoint',
    'DataResponse',
    'BaseDataSource',
    'YahooDataSource',
    'BinanceDataSource',
    'get_data_provider',
    'reset_data_provider',
    
    # Metrics Calculator
    'MetricsCalculator',
    'MetricsConfig',
    'MetricType',
    'AnnualizationMethod',
    'PerformanceMetrics',
    'RiskMetrics',
    'TradeMetrics',
    'PortfolioMetrics',
    'RollingMetrics',
    'get_metrics_calculator',
    'reset_metrics_calculator',
    
    # Monte Carlo Simulator
    'MonteCarloSimulator',
    'MonteCarloConfig',
    'SimulationMethod',
    'DistributionType',
    'MonteCarloResult',
    'MonteCarloStats',
    'get_monte_carlo',
    'reset_monte_carlo',
    
    # Optimizer
    'Optimizer',
    'OptimizerConfig',
    'OptimizerMethod',
    'ObjectiveType',
    'ParameterType',
    'Parameter',
    'OptimizationResult',
    'OptimizationProgress',
    'get_optimizer',
    'reset_optimizer',
    
    # Report Generator
    'ReportGenerator',
    'ReportConfig',
    'Report',
    'ReportFormat',
    'ReportType',
    'get_report_generator',
    'reset_report_generator',
    
    # Results Analyzer
    'ResultsAnalyzer',
    'AnalysisConfig',
    'AnalysisResult',
    'AnalysisType',
    'get_results_analyzer',
    'reset_results_analyzer',
    
    # Strategy Runner
    'StrategyRunner',
    'BaseStrategy',
    'TrendFollowingStrategy',
    'MeanReversionStrategy',
    'MomentumStrategy',
    'StrategyType',
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'Order',
    'Position',
    'Trade',
    'StrategyResult',
    'get_strategy_runner',
    'reset_strategy_runner',
    
    # Walk-Forward Analysis
    'WalkForwardAnalyzer',
    'WalkForwardConfig',
    'WalkForwardResult',
    'WalkForwardSummary',
    'WindowType',
    'get_walk_forward',
    'reset_walk_forward',
    
    # Registries
    'BACKTEST_COMPONENTS',
    'BACKTEST_CONFIG_SCHEMAS',
    
    # Version
    '__version__',
    '__author__',
    '__copyright__'
]

# ========================================
# COMPONENT INITIALIZATION
# ========================================

def initialize_backtesting() -> None:
    """Initialize all backtesting components"""
    logger = logging.getLogger(__name__)
    
    # Initialize components
    components = {
        'data_provider': get_data_provider,
        'metrics_calculator': get_metrics_calculator,
        'monte_carlo': get_monte_carlo,
        'optimizer': get_optimizer,
        'report_generator': get_report_generator,
        'results_analyzer': get_results_analyzer,
        'strategy_runner': get_strategy_runner,
        'walk_forward': get_walk_forward
    }
    
    for name, getter in components.items():
        try:
            component = getter()
            logger.info(f"Initialized {name}")
        except Exception as e:
            logger.error(f"Failed to initialize {name}: {e}")
    
    logger.info("Backtesting components initialized")


def shutdown_backtesting() -> None:
    """Shutdown all backtesting components"""
    logger = logging.getLogger(__name__)
    
    # Shutdown components
    components = {
        'data_provider': (get_data_provider, reset_data_provider),
        'metrics_calculator': (get_metrics_calculator, reset_metrics_calculator),
        'monte_carlo': (get_monte_carlo, reset_monte_carlo),
        'optimizer': (get_optimizer, reset_optimizer),
        'report_generator': (get_report_generator, reset_report_generator),
        'results_analyzer': (get_results_analyzer, reset_results_analyzer),
        'strategy_runner': (get_strategy_runner, reset_strategy_runner),
        'walk_forward': (get_walk_forward, reset_walk_forward)
    }
    
    for name, (getter, resetter) in components.items():
        try:
            resetter()
            logger.info(f"Shutdown {name}")
        except Exception as e:
            logger.error(f"Failed to shutdown {name}: {e}")
    
    logger.info("Backtesting components shutdown")

# ========================================
# CONTEXT MANAGER
# ========================================

class BacktestingContext:
    """Context manager for backtesting"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        """Enter context"""
        self.logger.info("Starting backtesting context")
        initialize_backtesting()
        
        # Start components
        components = [
            get_data_provider(),
            get_metrics_calculator(),
            get_monte_carlo(),
            get_optimizer(),
            get_report_generator(),
            get_results_analyzer(),
            get_strategy_runner(),
            get_walk_forward()
        ]
        
        for component in components:
            if hasattr(component, 'start'):
                try:
                    await component.start()
                    self.logger.info(f"Started {component.__class__.__name__}")
                except Exception as e:
                    self.logger.error(f"Failed to start {component.__class__.__name__}: {e}")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context"""
        self.logger.info("Stopping backtesting context")
        
        # Stop components
        components = [
            get_data_provider(),
            get_metrics_calculator(),
            get_monte_carlo(),
            get_optimizer(),
            get_report_generator(),
            get_results_analyzer(),
            get_strategy_runner(),
            get_walk_forward()
        ]
        
        for component in components:
            if hasattr(component, 'stop'):
                try:
                    await component.stop()
                    self.logger.info(f"Stopped {component.__class__.__name__}")
                except Exception as e:
                    self.logger.error(f"Failed to stop {component.__class__.__name__}: {e}")
        
        shutdown_backtesting()

# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

async def run_backtest(
    strategy: str,
    data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> BacktestResult:
    """
    Run a backtest with default settings.
    
    Args:
        strategy: Strategy name or configuration
        data: Historical data
        config: Backtest configuration
        
    Returns:
        BacktestResult: Backtest result
    """
    engine = get_backtest_engine()
    
    # Create config
    if not config:
        config = {
            'name': f"Backtest_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            'type': BacktestType.SINGLE,
            'start_date': data.get('start_date', datetime.utcnow() - timedelta(days=365)),
            'end_date': data.get('end_date', datetime.utcnow()),
            'symbols': data.get('symbols', ['BTC-USD']),
            'initial_capital': data.get('initial_capital', 100000),
            'strategy': strategy
        }
    
    backtest_config = BacktestConfig(**config)
    backtest_id = await engine.create_backtest(backtest_config)
    result = await engine.run_backtest(backtest_id)
    
    return result


async def optimize_strategy(
    strategy: str,
    data: Dict[str, Any],
    param_space: Dict[str, List[Any]],
    objective: str = 'sharpe_ratio',
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Optimize strategy parameters.
    
    Args:
        strategy: Strategy name
        data: Historical data
        param_space: Parameter space
        objective: Objective metric
        config: Optimization configuration
        
    Returns:
        Dict[str, Any]: Optimization results
    """
    optimizer = get_optimizer()
    
    # Create optimization config
    if not config:
        config = {
            'method': OptimizerMethod.RANDOM,
            'max_iterations': 100,
            'objective': ObjectiveType.MAXIMIZE
        }
    
    optimizer_config = OptimizerConfig(**config)
    
    # Define objective function
    def objective_function(params):
        # Run backtest with parameters
        result = await run_backtest(
            strategy,
            data,
            {'strategy_params': params}
        )
        return result.metrics.get(objective, 0)
    
    # Define parameters
    parameters = []
    for name, values in param_space.items():
        if all(isinstance(v, (int, float)) for v in values):
            if all(isinstance(v, int) for v in values):
                param_type = ParameterType.INTEGER
            else:
                param_type = ParameterType.FLOAT
            parameters.append(Parameter(
                name=name,
                type=param_type,
                min=min(values),
                max=max(values)
            ))
        else:
            parameters.append(Parameter(
                name=name,
                type=ParameterType.CATEGORICAL,
                choices=values
            ))
    
    # Run optimization
    result = await optimizer.optimize(
        objective_function=objective_function,
        parameters=parameters,
        method=optimizer_config.method,
        max_iterations=optimizer_config.max_iterations
    )
    
    return {
        'best_params': result.best_parameters,
        'best_score': result.best_objective,
        'history': result.history,
        'convergence': result.convergence
    }


async def run_monte_carlo(
    returns: List[float],
    initial_value: float = 100000.0,
    iterations: int = 10000,
    config: Optional[Dict[str, Any]] = None
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation.
    
    Args:
        returns: Historical returns
        initial_value: Initial value
        iterations: Number of iterations
        config: Simulation configuration
        
    Returns:
        MonteCarloResult: Simulation result
    """
    simulator = get_monte_carlo()
    
    # Create config
    if not config:
        config = {
            'method': SimulationMethod.HISTORICAL,
            'iterations': iterations
        }
    
    simulator.config = MonteCarloConfig(**config)
    
    result = await simulator.simulate(
        returns=returns,
        initial_value=initial_value,
        iterations=iterations
    )
    
    return result


async def generate_report(
    result: BacktestResult,
    format: ReportFormat = ReportFormat.HTML
) -> Report:
    """
    Generate a report from backtest results.
    
    Args:
        result: Backtest result
        format: Report format
        
    Returns:
        Report: Generated report
    """
    generator = get_report_generator()
    
    config = ReportConfig(
        name=f"Report_{result.id}",
        type=ReportType.BACKTEST,
        format=format,
        include_charts=True,
        include_trades=True,
        include_metrics=True,
        include_summary=True
    )
    
    data = {
        'metrics': result.metrics,
        'trades': result.trade_log,
        'equity_curve': result.equity_curve,
        'returns': result.daily_returns,
        'summary': {
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'win_rate': result.win_rate,
            'total_trades': result.total_trades
        }
    }
    
    report = await generator.generate_report(config, data)
    return report


# ========================================
# INITIALIZATION
# ========================================

logger = logging.getLogger(__name__)
logger.info(f"NEXUS Backtesting Package v{__version__} initialized")
logger.info(f"Available components: {list(BACKTEST_COMPONENTS.keys())}")

# Auto-initialize components
initialize_backtesting()

# ========================================
# END OF PACKAGE
# ========================================"""
NEXUS AI TRADING SYSTEM
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder
"""

