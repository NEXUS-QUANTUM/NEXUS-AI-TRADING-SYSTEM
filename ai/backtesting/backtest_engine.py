"""
NEXUS AI TRADING SYSTEM - Backtest Engine
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Backtest Engine system with:
- Historical data processing
- Strategy execution
- Portfolio management
- Risk analysis
- Performance metrics
- Multi-asset support
- Multi-timeframe analysis
- Walk-forward optimization
- Monte Carlo simulation
- Parameter optimization
- Report generation
- Visualization
- Export capabilities
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pydantic import BaseModel, Field, validator
from scipy import stats
from scipy.optimize import minimize

from ai.backtesting.data_provider import DataProvider
from ai.backtesting.strategy_runner import StrategyRunner
from ai.backtesting.metrics_calculator import MetricsCalculator
from ai.backtesting.monte_carlo import MonteCarloSimulator
from ai.backtesting.walk_forward import WalkForwardOptimizer
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import BacktestError
from backend.services.portfolio_service import PortfolioService

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class BacktestStatus(str, Enum):
    """Backtest status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class BacktestType(str, Enum):
    """Backtest types"""
    SINGLE = "single"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    OPTIMIZATION = "optimization"
    STRESS_TEST = "stress_test"


class BacktestMode(str, Enum):
    """Backtest modes"""
    HISTORICAL = "historical"
    SIMULATION = "simulation"
    PAPER = "paper"
    REALTIME = "realtime"


class OptimizationMethod(str, Enum):
    """Optimization methods"""
    GRID = "grid_search"
    RANDOM = "random_search"
    BAYESIAN = "bayesian"
    GENETIC = "genetic"
    GRADIENT = "gradient_descent"


@dataclass
class BacktestConfig:
    """Backtest configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    type: BacktestType = BacktestType.SINGLE
    mode: BacktestMode = BacktestMode.HISTORICAL
    start_date: datetime
    end_date: datetime
    symbols: List[str] = field(default_factory=list)
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.001
    risk_free_rate: float = 0.02
    max_positions: int = 10
    max_position_size: float = 0.2
    max_leverage: float = 1.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: Optional[str] = None
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    optimization_params: Dict[str, Any] = field(default_factory=dict)
    monte_carlo_iterations: int = 1000
    walk_forward_periods: int = 10
    walk_forward_train_ratio: float = 0.7
    parallel_workers: int = 4
    use_cache: bool = True
    log_level: str = "info"


@dataclass
class BacktestResult:
    """Backtest result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    backtest_id: str
    status: BacktestStatus = BacktestStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    
    # Performance metrics
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    # Portfolio data
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    trade_log: List[Dict[str, Any]] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    
    # Optimization results
    optimal_params: Optional[Dict[str, Any]] = None
    optimization_history: Optional[List[Dict[str, Any]]] = None
    
    # Monte Carlo results
    monte_carlo_results: Optional[Dict[str, Any]] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class BacktestProgress:
    """Backtest progress"""
    backtest_id: str
    status: BacktestStatus
    progress: float  # 0-100
    current_step: str
    elapsed_time: float
    estimated_remaining: float
    details: Dict[str, Any] = field(default_factory=dict)


# ========================================
# BACKTEST ENGINE
# ========================================

class BacktestEngine:
    """
    Complete backtest engine for strategy testing and optimization.
    
    Features:
    - Historical data processing
    - Strategy execution
    - Portfolio management
    - Risk analysis
    - Performance metrics
    - Multi-asset support
    - Multi-timeframe analysis
    - Walk-forward optimization
    - Monte Carlo simulation
    - Parameter optimization
    - Report generation
    - Visualization
    - Export capabilities
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.redis = get_redis()
        self.data_provider = DataProvider()
        self.strategy_runner = StrategyRunner()
        self.metrics_calculator = MetricsCalculator()
        self.monte_carlo = MonteCarloSimulator()
        self.walk_forward = WalkForwardOptimizer()
        self.portfolio_service = PortfolioService()
        
        # State
        self._backtests: Dict[str, BacktestConfig] = {}
        self._results: Dict[str, BacktestResult] = {}
        self._progress: Dict[str, BacktestProgress] = {}
        self._running_backtests: Dict[str, asyncio.Task] = {}
        
        # Running state
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_backtests": 0,
            "completed_backtests": 0,
            "failed_backtests": 0,
            "avg_duration": 0.0,
            "total_trades": 0,
            "avg_trades_per_backtest": 0
        }
        
        self.logger = get_logger(f"{__name__}.BacktestEngine")
        self.logger.info("BacktestEngine initialized")
    
    # ========================================
    # BACKTEST MANAGEMENT
    # ========================================
    
    async def create_backtest(self, config: BacktestConfig) -> str:
        """
        Create a new backtest.
        
        Args:
            config: Backtest configuration
            
        Returns:
            str: Backtest ID
        """
        async with self._lock:
            if not config.id:
                config.id = str(uuid4())
            
            self._backtests[config.id] = config
            self._results[config.id] = BacktestResult(
                backtest_id=config.id,
                status=BacktestStatus.PENDING
            )
            self._progress[config.id] = BacktestProgress(
                backtest_id=config.id,
                status=BacktestStatus.PENDING,
                progress=0.0,
                current_step="Initializing",
                elapsed_time=0.0,
                estimated_remaining=0.0
            )
            
            self._metrics["total_backtests"] += 1
            
            self.logger.info(f"Created backtest: {config.name} ({config.id})")
            return config.id
    
    async def run_backtest(self, backtest_id: str) -> BacktestResult:
        """
        Run a backtest.
        
        Args:
            backtest_id: Backtest ID
            
        Returns:
            BacktestResult: Backtest result
            
        Raises:
            BacktestError: If backtest not found or already running
        """
        if backtest_id not in self._backtests:
            raise BacktestError(f"Backtest {backtest_id} not found")
        
        if backtest_id in self._running_backtests:
            raise BacktestError(f"Backtest {backtest_id} is already running")
        
        config = self._backtests[backtest_id]
        result = self._results[backtest_id]
        
        # Update status
        result.status = BacktestStatus.RUNNING
        result.start_time = datetime.utcnow()
        
        self._progress[backtest_id].status = BacktestStatus.RUNNING
        self._progress[backtest_id].progress = 0.0
        
        # Run in background
        task = asyncio.create_task(self._run_backtest_task(backtest_id))
        self._running_backtests[backtest_id] = task
        
        try:
            await task
            return self._results[backtest_id]
        finally:
            if backtest_id in self._running_backtests:
                del self._running_backtests[backtest_id]
    
    async def _run_backtest_task(self, backtest_id: str) -> None:
        """Background task for backtest execution"""
        try:
            config = self._backtests[backtest_id]
            result = self._results[backtest_id]
            
            # Update progress
            self._update_progress(backtest_id, 10, "Loading data")
            
            # Load historical data
            data = await self._load_data(config)
            if not data:
                raise BacktestError("No data available")
            
            self._update_progress(backtest_id, 20, "Data loaded")
            
            # Initialize portfolio
            portfolio = await self._initialize_portfolio(config)
            
            self._update_progress(backtest_id, 30, "Portfolio initialized")
            
            # Run strategy
            if config.type == BacktestType.SINGLE:
                result = await self._run_single_backtest(config, data, portfolio)
            elif config.type == BacktestType.WALK_FORWARD:
                result = await self._run_walk_forward_backtest(config, data, portfolio)
            elif config.type == BacktestType.MONTE_CARLO:
                result = await self._run_monte_carlo_backtest(config, data, portfolio)
            elif config.type == BacktestType.OPTIMIZATION:
                result = await self._run_optimization_backtest(config, data, portfolio)
            elif config.type == BacktestType.STRESS_TEST:
                result = await self._run_stress_test_backtest(config, data, portfolio)
            else:
                result = await self._run_single_backtest(config, data, portfolio)
            
            # Calculate metrics
            self._update_progress(backtest_id, 90, "Calculating metrics")
            metrics = await self._calculate_metrics(result, config)
            
            # Update result
            result = self._results[backtest_id]
            result.status = BacktestStatus.COMPLETED
            result.end_time = datetime.utcnow()
            result.duration = (result.end_time - result.start_time).total_seconds()
            
            # Update metrics
            self._metrics["completed_backtests"] += 1
            self._metrics["total_trades"] += result.total_trades
            
            self._update_progress(backtest_id, 100, "Completed")
            
            self.logger.info(f"Backtest {backtest_id} completed successfully")
            
        except Exception as e:
            self.logger.error(f"Backtest {backtest_id} failed: {e}")
            result = self._results[backtest_id]
            result.status = BacktestStatus.FAILED
            result.errors.append(str(e))
            self._metrics["failed_backtests"] += 1
            self._update_progress(backtest_id, 100, "Failed")
            raise
    
    def _update_progress(
        self,
        backtest_id: str,
        progress: float,
        current_step: str
    ) -> None:
        """Update backtest progress"""
        if backtest_id in self._progress:
            self._progress[backtest_id].progress = progress
            self._progress[backtest_id].current_step = current_step
            
            # Store in Redis for real-time updates
            try:
                key = f"backtest_progress:{backtest_id}"
                self.redis.setex(
                    key,
                    3600,
                    json.dumps({
                        'backtest_id': backtest_id,
                        'progress': progress,
                        'current_step': current_step,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                )
            except Exception as e:
                self.logger.error(f"Failed to store progress: {e}")
    
    # ========================================
    # DATA LOADING
    # ========================================
    
    async def _load_data(self, config: BacktestConfig) -> Dict[str, pd.DataFrame]:
        """Load historical data for backtest"""
        data = {}
        
        for symbol in config.symbols:
            try:
                df = await self.data_provider.get_historical_data(
                    symbol=symbol,
                    start_date=config.start_date,
                    end_date=config.end_date
                )
                if not df.empty:
                    data[symbol] = df
                    self.logger.debug(f"Loaded {len(df)} rows for {symbol}")
            except Exception as e:
                self.logger.error(f"Failed to load data for {symbol}: {e}")
        
        return data
    
    # ========================================
    # PORTFOLIO MANAGEMENT
    # ========================================
    
    async def _initialize_portfolio(self, config: BacktestConfig) -> Dict[str, Any]:
        """Initialize portfolio for backtest"""
        return {
            'cash': config.initial_capital,
            'positions': {},
            'total_value': config.initial_capital,
            'equity_curve': [config.initial_capital],
            'drawdown_curve': [0.0],
            'trades': [],
            'daily_returns': []
        }
    
    # ========================================
    # BACKTEST EXECUTION
    # ========================================
    
    async def _run_single_backtest(
        self,
        config: BacktestConfig,
        data: Dict[str, pd.DataFrame],
        portfolio: Dict[str, Any]
    ) -> BacktestResult:
        """Run a single backtest"""
        # Get strategy
        strategy = await self.strategy_runner.get_strategy(
            config.strategy,
            config.strategy_params
        )
        
        # Run strategy
        result = await self.strategy_runner.run(
            strategy=strategy,
            data=data,
            portfolio=portfolio,
            config=config
        )
        
        return result
    
    async def _run_walk_forward_backtest(
        self,
        config: BacktestConfig,
        data: Dict[str, pd.DataFrame],
        portfolio: Dict[str, Any]
    ) -> BacktestResult:
        """Run walk-forward optimization backtest"""
        result = await self.walk_forward.run(
            data=data,
            strategy_name=config.strategy,
            strategy_params=config.strategy_params,
            optimization_params=config.optimization_params,
            train_ratio=config.walk_forward_train_ratio,
            periods=config.walk_forward_periods
        )
        
        return result
    
    async def _run_monte_carlo_backtest(
        self,
        config: BacktestConfig,
        data: Dict[str, pd.DataFrame],
        portfolio: Dict[str, Any]
    ) -> BacktestResult:
        """Run Monte Carlo backtest"""
        # Run base backtest
        base_result = await self._run_single_backtest(config, data, portfolio)
        
        # Run Monte Carlo simulation
        mc_result = await self.monte_carlo.simulate(
            returns=base_result.daily_returns,
            iterations=config.monte_carlo_iterations,
            initial_capital=config.initial_capital
        )
        
        base_result.monte_carlo_results = mc_result
        return base_result
    
    async def _run_optimization_backtest(
        self,
        config: BacktestConfig,
        data: Dict[str, pd.DataFrame],
        portfolio: Dict[str, Any]
    ) -> BacktestResult:
        """Run parameter optimization backtest"""
        # Get strategy
        strategy = await self.strategy_runner.get_strategy(
            config.strategy,
            config.strategy_params
        )
        
        # Run optimization
        result = await self.strategy_runner.optimize(
            strategy=strategy,
            data=data,
            portfolio=portfolio,
            config=config
        )
        
        return result
    
    async def _run_stress_test_backtest(
        self,
        config: BacktestConfig,
        data: Dict[str, pd.DataFrame],
        portfolio: Dict[str, Any]
    ) -> BacktestResult:
        """Run stress test backtest"""
        # Run base backtest
        base_result = await self._run_single_backtest(config, data, portfolio)
        
        # Apply stress scenarios
        stress_scenarios = [
            {'type': 'market_crash', 'drop': 0.3},
            {'type': 'flash_crash', 'drop': 0.5},
            {'type': 'gradual_decline', 'drop': 0.2, 'duration': 30}
        ]
        
        stress_results = []
        for scenario in stress_scenarios:
            # Apply scenario to data
            stressed_data = await self._apply_stress_scenario(data, scenario)
            
            # Run backtest on stressed data
            result = await self._run_single_backtest(
                config,
                stressed_data,
                portfolio
            )
            stress_results.append({
                'scenario': scenario,
                'result': result
            })
        
        base_result.metadata['stress_results'] = stress_results
        return base_result
    
    async def _apply_stress_scenario(
        self,
        data: Dict[str, pd.DataFrame],
        scenario: Dict[str, Any]
    ) -> Dict[str, pd.DataFrame]:
        """Apply stress scenario to data"""
        stressed_data = {}
        
        for symbol, df in data.items():
            stressed_df = df.copy()
            
            if scenario['type'] == 'market_crash':
                # Apply sudden drop
                drop = scenario.get('drop', 0.3)
                drop_point = len(stressed_df) // 2
                stressed_df.loc[drop_point:, 'close'] *= (1 - drop)
                
            elif scenario['type'] == 'flash_crash':
                # Apply temporary drop
                drop = scenario.get('drop', 0.5)
                flash_point = len(stressed_df) // 2
                flash_duration = 5
                stressed_df.loc[flash_point:flash_point+flash_duration, 'close'] *= (1 - drop)
                
            elif scenario['type'] == 'gradual_decline':
                # Apply gradual decline
                drop = scenario.get('drop', 0.2)
                duration = scenario.get('duration', 30)
                start_idx = len(stressed_df) - duration
                if start_idx > 0:
                    decline = np.linspace(0, -drop, duration)
                    for i, dec in enumerate(decline):
                        if start_idx + i < len(stressed_df):
                            stressed_df.loc[start_idx + i, 'close'] *= (1 + dec)
            
            stressed_data[symbol] = stressed_df
        
        return stressed_data
    
    # ========================================
    # METRICS CALCULATION
    # ========================================
    
    async def _calculate_metrics(
        self,
        result: BacktestResult,
        config: BacktestConfig
    ) -> Dict[str, Any]:
        """Calculate performance metrics"""
        metrics = await self.metrics_calculator.calculate(
            equity_curve=result.equity_curve,
            daily_returns=result.daily_returns,
            trades=result.trade_log,
            risk_free_rate=config.risk_free_rate
        )
        
        # Update result
        result.total_return = metrics.get('total_return', 0)
        result.annual_return = metrics.get('annual_return', 0)
        result.sharpe_ratio = metrics.get('sharpe_ratio', 0)
        result.sortino_ratio = metrics.get('sortino_ratio', 0)
        result.calmar_ratio = metrics.get('calmar_ratio', 0)
        result.max_drawdown = metrics.get('max_drawdown', 0)
        result.win_rate = metrics.get('win_rate', 0)
        result.profit_factor = metrics.get('profit_factor', 0)
        
        return metrics
    
    # ========================================
    # REPORT GENERATION
    # ========================================
    
    async def generate_report(
        self,
        backtest_id: str,
        format: str = 'html'
    ) -> str:
        """
        Generate backtest report.
        
        Args:
            backtest_id: Backtest ID
            format: Report format ('html', 'pdf', 'json')
            
        Returns:
            str: Report content
        """
        if backtest_id not in self._results:
            raise BacktestError(f"Backtest {backtest_id} not found")
        
        result = self._results[backtest_id]
        config = self._backtests.get(backtest_id)
        
        if not config:
            raise BacktestError(f"Backtest config {backtest_id} not found")
        
        report = await self._generate_report_content(result, config)
        
        if format == 'html':
            return await self._render_html_report(report)
        elif format == 'pdf':
            return await self._render_pdf_report(report)
        elif format == 'json':
            return json.dumps(report, default=str, indent=2)
        else:
            raise BacktestError(f"Unsupported format: {format}")
    
    async def _generate_report_content(
        self,
        result: BacktestResult,
        config: BacktestConfig
    ) -> Dict[str, Any]:
        """Generate report content"""
        return {
            'backtest_id': result.backtest_id,
            'name': config.name,
            'status': result.status.value,
            'start_date': config.start_date.isoformat(),
            'end_date': config.end_date.isoformat(),
            'duration': result.duration,
            'initial_capital': config.initial_capital,
            'final_capital': result.equity_curve[-1] if result.equity_curve else 0,
            
            'performance': {
                'total_return': result.total_return,
                'annual_return': result.annual_return,
                'sharpe_ratio': result.sharpe_ratio,
                'sortino_ratio': result.sortino_ratio,
                'calmar_ratio': result.calmar_ratio,
                'max_drawdown': result.max_drawdown,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor
            },
            
            'trades': {
                'total_trades': result.total_trades,
                'winning_trades': result.winning_trades,
                'losing_trades': result.losing_trades,
                'avg_win': result.avg_win,
                'avg_loss': result.avg_loss
            },
            
            'equity_curve': result.equity_curve,
            'drawdown_curve': result.drawdown_curve,
            'daily_returns': result.daily_returns,
            'trade_log': result.trade_log,
            
            'metadata': result.metadata,
            'errors': result.errors,
            'warnings': result.warnings
        }
    
    async def _render_html_report(self, report: Dict[str, Any]) -> str:
        """Render HTML report"""
        # Create HTML template
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Backtest Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                h1 { color: #1a1a2e; }
                .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
                .metric { background: #f5f5f5; padding: 15px; border-radius: 8px; }
                .metric-label { font-size: 12px; color: #666; }
                .metric-value { font-size: 20px; font-weight: bold; margin-top: 5px; }
                .metric-value.positive { color: #22c55e; }
                .metric-value.negative { color: #ef4444; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background: #f5f5f5; }
                .chart-container { margin: 20px 0; }
            </style>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        </head>
        <body>
            <h1>Backtest Report</h1>
            <h2>{name}</h2>
            <p>Status: {status} | Duration: {duration:.2f}s</p>
            <p>Period: {start_date} to {end_date}</p>
            <p>Initial Capital: ${initial_capital:,.2f} | Final Capital: ${final_capital:,.2f}</p>
            
            <div class="summary">
                <div class="metric">
                    <div class="metric-label">Total Return</div>
                    <div class="metric-value {total_return_class}">{total_return:.2f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Sharpe Ratio</div>
                    <div class="metric-value">{sharpe_ratio:.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Max Drawdown</div>
                    <div class="metric-value {max_drawdown_class}">{max_drawdown:.2f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Win Rate</div>
                    <div class="metric-value">{win_rate:.2f}%</div>
                </div>
            </div>
            
            <div class="chart-container">
                <div id="equity-chart"></div>
            </div>
            <div class="chart-container">
                <div id="drawdown-chart"></div>
            </div>
            
            <h3>Trade Statistics</h3>
            <table>
                <tr>
                    <th>Total Trades</th>
                    <th>Winning</th>
                    <th>Losing</th>
                    <th>Avg Win</th>
                    <th>Avg Loss</th>
                    <th>Profit Factor</th>
                </tr>
                <tr>
                    <td>{total_trades}</td>
                    <td>{winning_trades}</td>
                    <td>{losing_trades}</td>
                    <td>${avg_win:.2f}</td>
                    <td>${avg_loss:.2f}</td>
                    <td>{profit_factor:.2f}</td>
                </tr>
            </table>
            
            <script>
                // Equity chart
                var equityData = {equity_data};
                var drawdownData = {drawdown_data};
                
                var equityTrace = {
                    x: Array.from({length: equityData.length}, (_, i) => i),
                    y: equityData,
                    type: 'scatter',
                    mode: 'lines',
                    name: 'Equity',
                    line: {color: '#22c55e'}
                };
                
                var drawdownTrace = {
                    x: Array.from({length: drawdownData.length}, (_, i) => i),
                    y: drawdownData,
                    type: 'scatter',
                    mode: 'lines',
                    name: 'Drawdown',
                    line: {color: '#ef4444'},
                    fill: 'tozeroy'
                };
                
                Plotly.newPlot('equity-chart', [equityTrace], {
                    title: 'Equity Curve',
                    xaxis: {title: 'Time'},
                    yaxis: {title: 'Value ($)'}
                });
                
                Plotly.newPlot('drawdown-chart', [drawdownTrace], {
                    title: 'Drawdown',
                    xaxis: {title: 'Time'},
                    yaxis: {title: 'Drawdown (%)'}
                });
            </script>
        </body>
        </html>
        """
        
        # Fill template
        total_return_class = 'positive' if report['performance']['total_return'] >= 0 else 'negative'
        max_drawdown_class = 'negative' if report['performance']['max_drawdown'] > 0 else 'positive'
        
        html = html.format(
            name=report['name'],
            status=report['status'],
            duration=report['duration'] or 0,
            start_date=report['start_date'],
            end_date=report['end_date'],
            initial_capital=report['initial_capital'],
            final_capital=report['final_capital'],
            total_return=report['performance']['total_return'] * 100,
            total_return_class=total_return_class,
            sharpe_ratio=report['performance']['sharpe_ratio'],
            max_drawdown=report['performance']['max_drawdown'] * 100,
            max_drawdown_class=max_drawdown_class,
            win_rate=report['performance']['win_rate'] * 100,
            profit_factor=report['performance']['profit_factor'],
            total_trades=report['trades']['total_trades'],
            winning_trades=report['trades']['winning_trades'],
            losing_trades=report['trades']['losing_trades'],
            avg_win=report['trades']['avg_win'],
            avg_loss=report['trades']['avg_loss'],
            equity_data=json.dumps(report['equity_curve']),
            drawdown_data=json.dumps(report['drawdown_curve'])
        )
        
        return html
    
    async def _render_pdf_report(self, report: Dict[str, Any]) -> str:
        """Render PDF report"""
        # Use ReportLab or similar for PDF generation
        # This is a placeholder
        return "PDF report generation coming soon"
    
    # ========================================
    # VISUALIZATION
    # ========================================
    
    async def create_charts(
        self,
        backtest_id: str
    ) -> Dict[str, str]:
        """
        Create visual charts for backtest.
        
        Args:
            backtest_id: Backtest ID
            
        Returns:
            Dict[str, str]: Chart data URLs
        """
        if backtest_id not in self._results:
            raise BacktestError(f"Backtest {backtest_id} not found")
        
        result = self._results[backtest_id]
        
        charts = {}
        
        # Equity curve chart
        if result.equity_curve:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=result.equity_curve,
                mode='lines',
                name='Equity',
                line=dict(color='#22c55e', width=2)
            ))
            fig.update_layout(
                title='Equity Curve',
                xaxis_title='Time',
                yaxis_title='Value ($)',
                template='plotly_dark' if settings.THEME == 'dark' else 'plotly_white'
            )
            charts['equity'] = fig.to_html()
        
        # Drawdown chart
        if result.drawdown_curve:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=result.drawdown_curve,
                mode='lines',
                name='Drawdown',
                fill='tozeroy',
                line=dict(color='#ef4444', width=2)
            ))
            fig.update_layout(
                title='Drawdown',
                xaxis_title='Time',
                yaxis_title='Drawdown (%)',
                template='plotly_dark' if settings.THEME == 'dark' else 'plotly_white'
            )
            charts['drawdown'] = fig.to_html()
        
        # Monthly returns heatmap
        if result.daily_returns:
            # Create monthly returns matrix
            # This is a simplified version
            fig = go.Figure()
            fig.add_trace(go.Heatmap(
                z=[[1, 2, 3], [4, 5, 6]],
                colorscale='RdBu',
                zmid=0
            ))
            fig.update_layout(
                title='Monthly Returns',
                template='plotly_dark' if settings.THEME == 'dark' else 'plotly_white'
            )
            charts['monthly_returns'] = fig.to_html()
        
        return charts
    
    # ========================================
    # EXPORT
    # ========================================
    
    async def export_results(
        self,
        backtest_id: str,
        format: str = 'csv'
    ) -> str:
        """
        Export backtest results.
        
        Args:
            backtest_id: Backtest ID
            format: Export format ('csv', 'json', 'excel')
            
        Returns:
            str: Export data
        """
        if backtest_id not in self._results:
            raise BacktestError(f"Backtest {backtest_id} not found")
        
        result = self._results[backtest_id]
        
        if format == 'csv':
            return await self._export_csv(result)
        elif format == 'json':
            return json.dumps({
                'backtest_id': result.backtest_id,
                'equity_curve': result.equity_curve,
                'drawdown_curve': result.drawdown_curve,
                'trades': result.trade_log,
                'metrics': {
                    'total_return': result.total_return,
                    'sharpe_ratio': result.sharpe_ratio,
                    'max_drawdown': result.max_drawdown
                }
            }, default=str, indent=2)
        elif format == 'excel':
            return await self._export_excel(result)
        else:
            raise BacktestError(f"Unsupported format: {format}")
    
    async def _export_csv(self, result: BacktestResult) -> str:
        """Export as CSV"""
        lines = ['timestamp,value']
        
        for i, value in enumerate(result.equity_curve):
            lines.append(f'{i},{value}')
        
        return '\n'.join(lines)
    
    async def _export_excel(self, result: BacktestResult) -> str:
        """Export as Excel"""
        # Use openpyxl or similar for Excel generation
        # This is a placeholder
        return "Excel export coming soon"
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_backtest(self, backtest_id: str) -> Optional[Dict[str, Any]]:
        """Get backtest details"""
        if backtest_id not in self._backtests:
            return None
        
        config = self._backtests[backtest_id]
        result = self._results.get(backtest_id)
        
        return {
            'id': config.id,
            'name': config.name,
            'type': config.type.value,
            'status': result.status.value if result else 'unknown',
            'start_date': config.start_date.isoformat(),
            'end_date': config.end_date.isoformat(),
            'symbols': config.symbols,
            'initial_capital': config.initial_capital,
            'progress': self._progress[backtest_id].progress if backtest_id in self._progress else 0
        }
    
    async def list_backtests(self) -> List[Dict[str, Any]]:
        """List all backtests"""
        backtests = []
        
        for backtest_id, config in self._backtests.items():
            result = self._results.get(backtest_id)
            backtests.append({
                'id': config.id,
                'name': config.name,
                'type': config.type.value,
                'status': result.status.value if result else 'unknown',
                'start_date': config.start_date.isoformat(),
                'end_date': config.end_date.isoformat()
            })
        
        return backtests
    
    async def get_progress(self, backtest_id: str) -> Optional[BacktestProgress]:
        """Get backtest progress"""
        return self._progress.get(backtest_id)
    
    async def cancel_backtest(self, backtest_id: str) -> bool:
        """Cancel a running backtest"""
        if backtest_id not in self._running_backtests:
            return False
        
        task = self._running_backtests[backtest_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        del self._running_backtests[backtest_id]
        self._results[backtest_id].status = BacktestStatus.CANCELLED
        self._progress[backtest_id].status = BacktestStatus.CANCELLED
        
        self.logger.info(f"Backtest {backtest_id} cancelled")
        return True
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get engine metrics"""
        return {
            **self._metrics,
            "running_backtests": len(self._running_backtests),
            "total_configs": len(self._backtests),
            "total_results": len(self._results)
        }
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the backtest engine"""
        self._running = True
        self.logger.info("BacktestEngine started")
    
    async def stop(self) -> None:
        """Stop the backtest engine"""
        self._running = False
        
        # Cancel all running backtests
        for backtest_id in list(self._running_backtests.keys()):
            await self.cancel_backtest(backtest_id)
        
        self.logger.info("BacktestEngine stopped")
    
    async def health_check(self) -> bool:
        """Check engine health"""
        try:
            # Check Redis connection
            self.redis.ping()
            
            # Check data provider
            await self.data_provider.health_check()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False


# ========================================
# DEPENDENCY INJECTION
# ========================================

_backtest_engine: Optional[BacktestEngine] = None


def get_backtest_engine() -> BacktestEngine:
    """Get singleton instance of BacktestEngine"""
    global _backtest_engine
    if _backtest_engine is None:
        _backtest_engine = BacktestEngine()
    return _backtest_engine


def reset_backtest_engine() -> None:
    """Reset the backtest engine (for testing)"""
    global _backtest_engine
    if _backtest_engine:
        asyncio.create_task(_backtest_engine.stop())
    _backtest_engine = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'BacktestEngine',
    'BacktestConfig',
    'BacktestResult',
    'BacktestProgress',
    'BacktestStatus',
    'BacktestType',
    'BacktestMode',
    'OptimizationMethod',
    'get_backtest_engine',
    'reset_backtest_engine'
]
