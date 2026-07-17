# trading/bots/ai_bot/ai_bot_backtest.py
"""
NEXUS AI TRADING SYSTEM - Backtesting Engine
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements the backtesting engine for the AI Trading Bot.
Provides comprehensive backtesting capabilities including:
    - Historical data simulation
    - Strategy validation and optimization
    - Performance metrics calculation
    - Risk analysis
    - Walk-forward analysis
    - Monte Carlo simulation
    - Parameter optimization
    - Multi-asset backtesting
    - Realistic order execution simulation
    - Slippage and commission modeling
    - Performance reporting and visualization
"""

import os
import sys
import json
import yaml
import asyncio
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# Import bot components
from trading.bots.ai_bot.ai_bot import AIBot, BotConfig, BotStatus, BotMode
from trading.bots.ai_bot.config import load_config
from trading.bots.ai_bot.data_pipeline import DataPipeline
from trading.bots.ai_bot.execution_engine import ExecutionEngine
from trading.bots.ai_bot.risk_manager import RiskManager
from trading.bots.ai_bot.strategy_engine import StrategyEngine
from trading.bots.ai_bot.model_manager import ModelManager
from trading.bots.ai_bot.performance_tracker import PerformanceTracker

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class BacktestMode(Enum):
    """Backtest execution mode."""
    SINGLE = "single"          # Single run
    OPTIMIZE = "optimize"      # Parameter optimization
    WALK_FORWARD = "walk_forward"  # Walk-forward analysis
    MONTE_CARLO = "monte_carlo"    # Monte Carlo simulation
    STRESS = "stress"          # Stress testing


class BacktestStatus(Enum):
    """Backtest status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class BacktestConfig:
    """Backtest configuration."""
    mode: BacktestMode = BacktestMode.SINGLE
    start_date: datetime = field(default_factory=lambda: datetime.now() - timedelta(days=365))
    end_date: datetime = field(default_factory=lambda: datetime.now())
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.001
    benchmark: Optional[str] = None
    iterations: int = 1
    optimization_metric: str = "sharpe_ratio"
    walk_forward_periods: int = 12
    monte_carlo_simulations: int = 1000
    confidence_level: float = 0.95
    output_dir: Optional[str] = None
    save_results: bool = True
    verbose: bool = True


@dataclass
class BacktestResult:
    """Backtest result container."""
    name: str
    status: BacktestStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    
    # Performance metrics
    total_return: float = 0.0
    annual_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: float = 0.0
    
    # Trading metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    average_trade: float = 0.0
    expectancy: float = 0.0
    
    # Additional metrics
    total_volume: float = 0.0
    total_fees: float = 0.0
    total_slippage: float = 0.0
    
    # Data
    equity_curve: Optional[pd.Series] = None
    trades: Optional[List[Dict[str, Any]]] = None
    orders: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'name': self.name,
            'status': self.status.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'total_return': self.total_return,
            'annual_return': self.annual_return,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'average_win': self.average_win,
            'average_loss': self.average_loss,
            'average_trade': self.average_trade,
            'expectancy': self.expectancy,
            'total_volume': self.total_volume,
            'total_fees': self.total_fees,
            'total_slippage': self.total_slippage,
            'parameters': self.parameters
        }


@dataclass
class OptimizationResult:
    """Parameter optimization result."""
    best_params: Dict[str, Any]
    best_score: float
    all_results: List[Dict[str, Any]]
    iterations: int
    optimization_metric: str


# =============================================================================
# Backtesting Engine
# =============================================================================

class BacktestEngine:
    """
    Comprehensive backtesting engine for AI Trading Bot.
    
    This engine simulates historical trading to evaluate strategy performance,
    optimize parameters, and analyze risk. It supports multiple backtest modes
    and provides detailed performance metrics.
    
    Usage:
        # Create backtest engine
        engine = BacktestEngine(config)
        
        # Run single backtest
        result = await engine.run_backtest(strategy, data)
        
        # Run parameter optimization
        results = await engine.run_optimization(strategy, data, param_grid)
        
        # Run walk-forward analysis
        results = await engine.run_walk_forward(strategy, data)
    """
    
    def __init__(
        self,
        config: Union[Dict[str, Any], BacktestConfig, str, Path],
        bot_config: Optional[Union[Dict[str, Any], BotConfig]] = None
    ):
        """
        Initialize the backtest engine.
        
        Args:
            config: Backtest configuration
            bot_config: Bot configuration for the backtest
        """
        # Load configuration
        if isinstance(config, dict):
            self.config = BacktestConfig(**config)
        elif isinstance(config, BacktestConfig):
            self.config = config
        elif isinstance(config, (str, Path)):
            self.config = self._load_config_from_file(config)
        else:
            raise ValueError("Invalid config type")
        
        # Bot configuration
        if bot_config is None:
            self.bot_config = {}
        elif isinstance(bot_config, dict):
            self.bot_config = bot_config
        elif isinstance(bot_config, BotConfig):
            self.bot_config = bot_config.to_dict()
        else:
            raise ValueError("Invalid bot_config type")
        
        # Set up logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Results storage
        self.results = []
        self.current_result = None
        
        # Progress tracking
        self.progress = 0
        self.is_running = False
        
        self.logger.info("Backtest engine initialized")
    
    def _load_config_from_file(self, file_path: Union[str, Path]) -> BacktestConfig:
        """Load backtest configuration from file."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            if file_path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif file_path.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        return BacktestConfig(**data)
    
    # =========================================================================
    # Main Backtest Methods
    # =========================================================================
    
    async def run_backtest(
        self,
        strategy: Union[str, Any],
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        parameters: Optional[Dict[str, Any]] = None
    ) -> BacktestResult:
        """
        Run a single backtest.
        
        Args:
            strategy: Strategy instance or name
            data: Historical data
            parameters: Strategy parameters
            
        Returns:
            BacktestResult object
        """
        self.is_running = True
        self.progress = 0
        
        try:
            # Initialize backtest
            result = BacktestResult(
                name=f"Backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                status=BacktestStatus.RUNNING,
                start_time=datetime.now(),
                parameters=parameters
            )
            self.current_result = result
            
            # Prepare data
            self.progress = 10
            prepared_data = await self._prepare_data(data)
            
            # Initialize bot for backtest
            self.progress = 20
            bot = await self._initialize_bot(strategy, parameters)
            
            # Run simulation
            self.progress = 30
            results = await self._simulate(bot, prepared_data)
            
            # Calculate metrics
            self.progress = 80
            metrics = await self._calculate_metrics(results)
            
            # Update result
            self.progress = 90
            result.end_time = datetime.now()
            result.duration = (result.end_time - result.start_time).total_seconds()
            result.status = BacktestStatus.COMPLETED
            result.equity_curve = results.get('equity_curve')
            result.trades = results.get('trades', [])
            result.orders = results.get('orders', [])
            result.metrics = metrics
            
            # Update result fields from metrics
            for key, value in metrics.items():
                if hasattr(result, key):
                    setattr(result, key, value)
            
            # Save results
            if self.config.save_results:
                await self._save_result(result)
            
            self.results.append(result)
            self.is_running = False
            self.progress = 100
            
            self.logger.info(f"Backtest completed: {result.name}")
            return result
            
        except Exception as e:
            self.logger.error(f"Backtest failed: {e}")
            if self.current_result:
                self.current_result.status = BacktestStatus.FAILED
                self.current_result.end_time = datetime.now()
            self.is_running = False
            raise
    
    async def run_optimization(
        self,
        strategy: Union[str, Any],
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        param_grid: Dict[str, List[Any]],
        n_iterations: Optional[int] = None
    ) -> OptimizationResult:
        """
        Run parameter optimization.
        
        Args:
            strategy: Strategy instance or name
            data: Historical data
            param_grid: Parameter grid to search
            n_iterations: Number of iterations for random search
            
        Returns:
            OptimizationResult object
        """
        self.logger.info("Starting parameter optimization...")
        
        # Generate parameter combinations
        param_combinations = self._generate_param_combinations(param_grid, n_iterations)
        results = []
        best_score = -float('inf')
        best_params = None
        
        # Run backtests for each parameter combination
        total = len(param_combinations)
        for i, params in enumerate(tqdm(param_combinations, desc="Optimizing")):
            try:
                result = await self.run_backtest(strategy, data, params)
                
                # Extract score
                score = getattr(result, self.config.optimization_metric, 0)
                if score is None:
                    score = 0
                
                results.append({
                    'params': params,
                    'score': score,
                    'result': result
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params
                
                self.progress = (i + 1) / total * 100
                
            except Exception as e:
                self.logger.warning(f"Optimization iteration {i} failed: {e}")
                continue
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_results=results,
            iterations=len(param_combinations),
            optimization_metric=self.config.optimization_metric
        )
    
    async def run_walk_forward(
        self,
        strategy: Union[str, Any],
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        periods: Optional[int] = None
    ) -> List[BacktestResult]:
        """
        Run walk-forward analysis.
        
        Args:
            strategy: Strategy instance or name
            data: Historical data
            periods: Number of periods
            
        Returns:
            List of BacktestResult objects
        """
        if periods is None:
            periods = self.config.walk_forward_periods
        
        self.logger.info(f"Starting walk-forward analysis with {periods} periods...")
        
        # Split data into periods
        period_data = self._split_into_periods(data, periods)
        results = []
        
        for i, (train_data, test_data) in enumerate(period_data):
            self.logger.info(f"Period {i+1}/{periods}")
            
            # Optimize on train data
            param_grid = self._get_default_param_grid(strategy)
            opt_results = await self.run_optimization(
                strategy, train_data, param_grid, n_iterations=20
            )
            
            # Test on test data
            result = await self.run_backtest(
                strategy, test_data, opt_results.best_params
            )
            result.name = f"WalkForward_Period_{i+1}"
            results.append(result)
        
        return results
    
    async def run_monte_carlo(
        self,
        strategy: Union[str, Any],
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        n_simulations: Optional[int] = None
    ) -> List[BacktestResult]:
        """
        Run Monte Carlo simulation.
        
        Args:
            strategy: Strategy instance or name
            data: Historical data
            n_simulations: Number of simulations
            
        Returns:
            List of BacktestResult objects
        """
        if n_simulations is None:
            n_simulations = self.config.monte_carlo_simulations
        
        self.logger.info(f"Starting Monte Carlo simulation with {n_simulations} simulations...")
        
        # Generate random paths
        paths = self._generate_monte_carlo_paths(data, n_simulations)
        results = []
        
        for i, path in enumerate(tqdm(paths, desc="Monte Carlo")):
            try:
                result = await self.run_backtest(strategy, path)
                result.name = f"MonteCarlo_Sim_{i+1}"
                results.append(result)
            except Exception as e:
                self.logger.warning(f"Monte Carlo simulation {i} failed: {e}")
                continue
        
        return results
    
    # =========================================================================
    # Core Simulation Methods
    # =========================================================================
    
    async def _prepare_data(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]]
    ) -> Dict[str, pd.DataFrame]:
        """Prepare data for backtest."""
        if isinstance(data, pd.DataFrame):
            return {'default': data}
        elif isinstance(data, dict):
            return data
        else:
            raise ValueError("Invalid data format")
    
    async def _initialize_bot(
        self,
        strategy: Union[str, Any],
        parameters: Optional[Dict[str, Any]]
    ) -> AIBot:
        """Initialize bot for backtest."""
        # Create bot configuration
        bot_config = self.bot_config.copy()
        bot_config.update({
            'mode': BotMode.BACKTEST.value,
            'initial_capital': self.config.initial_capital,
            'commission': self.config.commission,
            'slippage': self.config.slippage,
        })
        
        # Add strategy
        if isinstance(strategy, str):
            bot_config['strategy'] = {'name': strategy, 'parameters': parameters}
        else:
            bot_config['strategy'] = {
                'name': strategy.__class__.__name__,
                'parameters': parameters or {}
            }
        
        # Create bot
        bot = AIBot(bot_config)
        return bot
    
    async def _simulate(
        self,
        bot: AIBot,
        data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Run the simulation."""
        # Start bot
        await bot.start()
        
        results = {
            'equity_curve': [],
            'trades': [],
            'orders': [],
            'timestamps': []
        }
        
        equity = self.config.initial_capital
        results['equity_curve'].append(equity)
        
        # Process each symbol
        for symbol, symbol_data in data.items():
            self.logger.debug(f"Processing {symbol}...")
            
            # Process each data point
            for idx, row in symbol_data.iterrows():
                # Update market data
                market_data = {
                    'symbol': symbol,
                    'timestamp': row.get('timestamp', idx),
                    'open': row.get('open', 0),
                    'high': row.get('high', 0),
                    'low': row.get('low', 0),
                    'close': row.get('close', 0),
                    'volume': row.get('volume', 0)
                }
                
                # Process data point
                try:
                    # Generate signal
                    signal = await bot._generate_signal(
                        {'price': market_data['close']},
                        pd.DataFrame([market_data])
                    )
                    
                    if signal and signal.get('signal') != 'hold':
                        # Execute trade
                        trade = await bot._execute_trade(signal)
                        if trade:
                            results['trades'].append(trade)
                            # Update equity
                            equity += trade.get('pnl', 0)
                            results['equity_curve'].append(equity)
                            results['timestamps'].append(market_data['timestamp'])
                    
                except Exception as e:
                    self.logger.warning(f"Error processing data point: {e}")
                    continue
        
        # Stop bot
        await bot.stop()
        
        return results
    
    async def _calculate_metrics(
        self,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate performance metrics."""
        trades = results.get('trades', [])
        equity_curve = results.get('equity_curve', [])
        
        if not trades:
            return self._empty_metrics()
        
        # Basic metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0
        
        # PnL metrics
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        avg_win = sum(t.get('pnl', 0) for t in winning_trades) / win_count if win_count > 0 else 0
        avg_loss = sum(t.get('pnl', 0) for t in losing_trades) / loss_count if loss_count > 0 else 0
        avg_trade = total_pnl / total_trades if total_trades > 0 else 0
        
        # Profit factor
        gross_profit = sum(t.get('pnl', 0) for t in winning_trades)
        gross_loss = abs(sum(t.get('pnl', 0) for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Drawdown
        max_drawdown, max_drawdown_duration = self._calculate_drawdown(equity_curve)
        
        # Sharpe ratio (assuming risk-free rate of 0)
        returns = pd.Series(equity_curve).pct_change().dropna()
        avg_return = returns.mean()
        std_return = returns.std()
        sharpe_ratio = avg_return / std_return * np.sqrt(252) if std_return > 0 else 0
        
        # Sortino ratio
        negative_returns = returns[returns < 0]
        std_negative = negative_returns.std()
        sortino_ratio = avg_return / std_negative * np.sqrt(252) if std_negative > 0 else 0
        
        # Calmar ratio
        calmar_ratio = (equity_curve[-1] / equity_curve[0] - 1) / max_drawdown if max_drawdown > 0 else 0
        
        return {
            'total_return': (equity_curve[-1] / equity_curve[0] - 1) if equity_curve else 0,
            'annual_return': self._annualize_return(equity_curve) if equity_curve else 0,
            'volatility': returns.std() * np.sqrt(252) if len(returns) > 0 else 0,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_duration': max_drawdown_duration,
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'average_win': avg_win,
            'average_loss': avg_loss,
            'average_trade': avg_trade,
            'expectancy': win_rate * avg_win - (1 - win_rate) * abs(avg_loss),
            'total_volume': sum(t.get('volume', 0) for t in trades),
            'total_fees': sum(t.get('fees', 0) for t in trades),
            'total_slippage': sum(t.get('slippage', 0) for t in trades)
        }
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics."""
        return {
            'total_return': 0.0,
            'annual_return': 0.0,
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'calmar_ratio': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_duration': 0.0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0,
            'average_trade': 0.0,
            'expectancy': 0.0,
            'total_volume': 0.0,
            'total_fees': 0.0,
            'total_slippage': 0.0
        }
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _calculate_drawdown(
        self,
        equity_curve: List[float]
    ) -> Tuple[float, float]:
        """Calculate maximum drawdown and duration."""
        if not equity_curve:
            return 0.0, 0.0
        
        peak = equity_curve[0]
        max_drawdown = 0.0
        max_duration = 0.0
        current_duration = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
                current_duration = 0
            else:
                drawdown = (peak - value) / peak
                max_drawdown = max(max_drawdown, drawdown)
                current_duration += 1
                max_duration = max(max_duration, current_duration)
        
        return max_drawdown, max_duration
    
    def _annualize_return(self, equity_curve: List[float]) -> float:
        """Annualize return."""
        if len(equity_curve) < 2:
            return 0.0
        
        total_return = equity_curve[-1] / equity_curve[0] - 1
        periods = len(equity_curve)
        years = periods / (252 * 24)  # Assuming hourly data
        return (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    
    def _generate_param_combinations(
        self,
        param_grid: Dict[str, List[Any]],
        n_iterations: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Generate parameter combinations."""
        import itertools
        
        if n_iterations is None:
            # Full grid search
            keys = list(param_grid.keys())
            values = list(param_grid.values())
            combinations = list(itertools.product(*values))
            return [dict(zip(keys, combo)) for combo in combinations]
        else:
            # Random search
            import random
            combinations = []
            for _ in range(n_iterations):
                params = {
                    key: random.choice(values)
                    for key, values in param_grid.items()
                }
                combinations.append(params)
            return combinations
    
    def _get_default_param_grid(self, strategy: Any) -> Dict[str, List[Any]]:
        """Get default parameter grid for a strategy."""
        # Default grids for common strategies
        strategy_name = strategy if isinstance(strategy, str) else strategy.__class__.__name__
        
        default_grids = {
            'MovingAverageCrossover': {
                'fast_period': [5, 10, 15, 20, 30],
                'slow_period': [20, 30, 50, 100, 200],
                'signal_period': [5, 10, 15]
            },
            'RSIStrategy': {
                'period': [7, 10, 14, 20, 30],
                'overbought': [60, 70, 80],
                'oversold': [20, 30, 40]
            },
            'MACDStrategy': {
                'fast_period': [6, 8, 12, 15],
                'slow_period': [13, 19, 26, 30],
                'signal_period': [5, 7, 9, 12]
            },
            'BollingerBandsStrategy': {
                'period': [10, 15, 20, 30, 50],
                'std_dev': [1.5, 2.0, 2.5, 3.0]
            }
        }
        
        return default_grids.get(strategy_name, {})
    
    def _split_into_periods(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        periods: int
    ) -> List[Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]]:
        """Split data into periods for walk-forward."""
        if isinstance(data, pd.DataFrame):
            data_dict = {'default': data}
        else:
            data_dict = data
        
        result = []
        n_rows = min(len(df) for df in data_dict.values())
        period_size = n_rows // periods
        
        for i in range(periods):
            start_idx = i * period_size
            end_idx = (i + 1) * period_size
            
            if i < periods - 1:
                # Split 80/20 for train/test
                split_idx = start_idx + int(period_size * 0.8)
                train = {k: v.iloc[:split_idx] for k, v in data_dict.items()}
                test = {k: v.iloc[split_idx:end_idx] for k, v in data_dict.items()}
            else:
                train = {k: v.iloc[:start_idx] for k, v in data_dict.items()}
                test = {k: v.iloc[start_idx:] for k, v in data_dict.items()}
            
            result.append((train, test))
        
        return result
    
    def _generate_monte_carlo_paths(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        n_simulations: int
    ) -> List[Dict[str, pd.DataFrame]]:
        """Generate Monte Carlo paths."""
        if isinstance(data, pd.DataFrame):
            data_dict = {'default': data}
        else:
            data_dict = data
        
        # Calculate returns
        returns_dict = {}
        for symbol, df in data_dict.items():
            returns = df['close'].pct_change().dropna()
            returns_dict[symbol] = {
                'returns': returns,
                'mean': returns.mean(),
                'std': returns.std()
            }
        
        paths = []
        for _ in range(n_simulations):
            path = {}
            for symbol, info in returns_dict.items():
                # Generate random returns
                random_returns = np.random.normal(
                    info['mean'],
                    info['std'],
                    len(info['returns'])
                )
                
                # Generate price path
                start_price = data_dict[symbol]['close'].iloc[-1]
                price_path = start_price * np.exp(np.cumsum(random_returns))
                
                # Create DataFrame
                df = data_dict[symbol].copy()
                df['close'] = price_path
                path[symbol] = df
            
            paths.append(path)
        
        return paths
    
    async def _save_result(self, result: BacktestResult) -> None:
        """Save backtest result."""
        if not self.config.output_dir:
            return
        
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = result.start_time.strftime('%Y%m%d_%H%M%S')
        
        # Save results as JSON
        result_file = output_dir / f"backtest_{timestamp}.json"
        with open(result_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        
        # Save equity curve if available
        if result.equity_curve is not None:
            equity_file = output_dir / f"equity_{timestamp}.csv"
            result.equity_curve.to_csv(equity_file)
        
        # Save trades if available
        if result.trades:
            trades_file = output_dir / f"trades_{timestamp}.csv"
            pd.DataFrame(result.trades).to_csv(trades_file, index=False)
        
        self.logger.info(f"Results saved to {output_dir}")
    
    # =========================================================================
    # Visualization Methods
    # =========================================================================
    
    def plot_results(
        self,
        result: BacktestResult,
        save_path: Optional[str] = None,
        show: bool = True
    ) -> None:
        """
        Plot backtest results.
        
        Args:
            result: Backtest result to plot
            save_path: Path to save the plot
            show: Whether to show the plot
        """
        if result.equity_curve is None:
            self.logger.warning("No equity curve available for plotting")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Equity curve
        ax1 = axes[0, 0]
        ax1.plot(result.equity_curve.index, result.equity_curve)
        ax1.set_title('Equity Curve')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Equity')
        ax1.grid(True)
        
        # Drawdown
        ax2 = axes[0, 1]
        peak = result.equity_curve.expanding().max()
        drawdown = (peak - result.equity_curve) / peak * 100
        ax2.fill_between(drawdown.index, 0, drawdown, color='red', alpha=0.3)
        ax2.set_title('Drawdown')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True)
        
        # Returns histogram
        ax3 = axes[1, 0]
        returns = result.equity_curve.pct_change().dropna() * 100
        ax3.hist(returns, bins=50, edgecolor='black')
        ax3.set_title('Returns Distribution')
        ax3.set_xlabel('Return (%)')
        ax3.set_ylabel('Frequency')
        ax3.grid(True)
        
        # Performance metrics
        ax4 = axes[1, 1]
        metrics = {
            'Total Return': f"{result.total_return * 100:.2f}%",
            'Annual Return': f"{result.annual_return * 100:.2f}%",
            'Sharpe Ratio': f"{result.sharpe_ratio:.2f}",
            'Max Drawdown': f"{result.max_drawdown * 100:.2f}%",
            'Win Rate': f"{result.win_rate * 100:.2f}%",
            'Profit Factor': f"{result.profit_factor:.2f}",
            'Total Trades': str(result.total_trades),
            'Expectancy': f"${result.expectancy:.2f}"
        }
        ax4.axis('off')
        ax4.text(0.1, 0.95, 'Performance Summary', fontsize=14, fontweight='bold')
        y_pos = 0.85
        for key, value in metrics.items():
            ax4.text(0.1, y_pos, f'{key}:', fontweight='bold')
            ax4.text(0.6, y_pos, value)
            y_pos -= 0.06
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Plot saved to {save_path}")
        
        if show:
            plt.show()
        
        plt.close()
    
    def compare_results(
        self,
        results: List[BacktestResult],
        save_path: Optional[str] = None,
        show: bool = True
    ) -> None:
        """
        Compare multiple backtest results.
        
        Args:
            results: List of backtest results
            save_path: Path to save the plot
            show: Whether to show the plot
        """
        if not results:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Equity curves
        ax1 = axes[0, 0]
        for result in results:
            if result.equity_curve is not None:
                normalized = result.equity_curve / result.equity_curve.iloc[0]
                ax1.plot(normalized.index, normalized, label=result.name[:20])
        ax1.set_title('Equity Curves (Normalized)')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Equity')
        ax1.legend()
        ax1.grid(True)
        
        # Performance metrics heatmap
        ax2 = axes[0, 1]
        metrics_data = []
        for result in results:
            metrics_data.append([
                result.total_return,
                result.sharpe_ratio,
                1 - result.max_drawdown,
                result.win_rate,
                result.profit_factor
            ])
        metrics_df = pd.DataFrame(
            metrics_data,
            columns=['Return', 'Sharpe', 'Drawdown', 'Win Rate', 'Profit Factor']
        )
        sns.heatmap(metrics_df, ax=ax2, annot=True, fmt='.2f', cmap='RdYlGn')
        ax2.set_title('Performance Metrics Comparison')
        ax2.set_xticklabels(ax2.get_xticklabels(), rotation=45)
        
        # Metrics bar chart
        ax3 = axes[1, 0]
        x = range(len(results))
        ax3.bar(x, [r.total_return for r in results], alpha=0.7, label='Return')
        ax3.set_title('Total Return')
        ax3.set_xlabel('Strategy')
        ax3.set_ylabel('Return')
        ax3.set_xticks(x)
        ax3.set_xticklabels([r.name[:10] for r in results], rotation=45)
        ax3.grid(True)
        
        # Scatter plot: Return vs Risk
        ax4 = axes[1, 1]
        for result in results:
            ax4.scatter(
                result.max_drawdown,
                result.total_return,
                s=100,
                label=result.name[:20]
            )
        ax4.set_title('Return vs Risk')
        ax4.set_xlabel('Max Drawdown')
        ax4.set_ylabel('Total Return')
        ax4.legend()
        ax4.grid(True)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Comparison plot saved to {save_path}")
        
        if show:
            plt.show()
        
        plt.close()
    
    # =========================================================================
    # Status and Information
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get backtest engine status."""
        return {
            'is_running': self.is_running,
            'progress': self.progress,
            'current_result': self.current_result.to_dict() if self.current_result else None,
            'results_count': len(self.results),
            'config': asdict(self.config)
        }
    
    def get_results(self) -> List[BacktestResult]:
        """Get all backtest results."""
        return self.results
    
    def get_best_result(self) -> Optional[BacktestResult]:
        """Get the best backtest result."""
        if not self.results:
            return None
        
        return max(self.results, key=lambda r: r.sharpe_ratio)
    
    def clear_results(self) -> None:
        """Clear all backtest results."""
        self.results = []
        self.current_result = None
        self.progress = 0


# =============================================================================
# Factory Function
# =============================================================================

def create_backtest_engine(
    config: Union[Dict[str, Any], BacktestConfig, str, Path],
    bot_config: Optional[Union[Dict[str, Any], BotConfig]] = None,
    auto_start: bool = False
) -> BacktestEngine:
    """
    Factory function to create a backtest engine.
    
    Args:
        config: Backtest configuration
        bot_config: Bot configuration
        auto_start: Whether to auto-start the engine
        
    Returns:
        BacktestEngine instance
    """
    engine = BacktestEngine(config, bot_config)
    
    if auto_start:
        engine.logger.info("Auto-starting backtest engine...")
    
    return engine


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'BacktestEngine',
    'BacktestConfig',
    'BacktestMode',
    'BacktestStatus',
    'BacktestResult',
    'OptimizationResult',
    'create_backtest_engine'
]


# =============================================================================
# Module Docstring
# =============================================================================

__doc__ = f"""
{__name__} - NEXUS AI Trading Bot Backtesting Engine

This module provides comprehensive backtesting capabilities for the
NEXUS AI Trading Bot, allowing for strategy validation, optimization,
and performance analysis.

Copyright: {__copyright__}
CEO: {__author__}
Version: {__version__}

Features:
    - Single backtest runs
    - Parameter optimization
    - Walk-forward analysis
    - Monte Carlo simulation
    - Detailed performance metrics
    - Visualizations and reporting
"""

# Log module initialization
logger.info(f"Backtest engine module loaded (version {__version__})")
