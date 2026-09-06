"""
tests/performance/test_backtest_perf.py

NEXUS AI Trading System - Backtesting Performance Tests

This module uses pytest-benchmark to measure the performance of the backtesting
engine, including strategy execution, metric calculation, and optimization.

It tests:
- Backtest execution for different data sizes (bars count)
- Performance with various timeframes (1h, 1d, 1w)
- Strategy complexity (simple moving average vs. ensemble)
- Metrics computation (Sharpe, drawdown, Calmar, etc.)
- Monte Carlo simulation performance
- Walk-forward analysis performance
- Optimization (grid search, Bayesian) speed

These benchmarks help identify bottlenecks in the backtesting pipeline and
track performance regressions over time.

Usage:
    pytest tests/performance/test_backtest_perf.py -v --benchmark-autosave
    pytest tests/performance/test_backtest_perf.py -v --benchmark-compare

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import pytest
import random
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from tests.performance.conftest import perf_benchmark_rounds

# Import backtesting modules
from backend.ai.backtesting.backtest_engine import BacktestEngine
from backend.ai.backtesting.strategy_runner import StrategyRunner
from backend.ai.backtesting.metrics_calculator import MetricsCalculator
from backend.ai.backtesting.monte_carlo import MonteCarloSimulator
from backend.ai.backtesting.optimizer import GridSearchOptimizer, BayesianOptimizer
from backend.ai.backtesting.walk_forward import WalkForwardAnalyzer
from backend.ai.strategies.base_strategy import BaseStrategy
from backend.ai.strategies.momentum_strategy import MomentumStrategy
from backend.ai.strategies.mean_reversion_strategy import MeanReversionStrategy
from backend.ai.strategies.breakout_strategy import BreakoutStrategy
from backend.ai.strategies.ensemble_strategy import EnsembleStrategy


# ----- Helper functions to generate test data -----

def generate_price_data(
    start_date: datetime,
    periods: int,
    freq: str = "1h",
    volatility: float = 0.02,
    trend: float = 0.0001,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic price data for backtesting."""
    np.random.seed(seed)
    dates = pd.date_range(start=start_date, periods=periods, freq=freq)
    returns = np.random.normal(trend, volatility, periods)
    price = 100.0 * np.exp(np.cumsum(returns))
    # Add some noise and patterns
    data = pd.DataFrame({
        "open": price * (1 + np.random.normal(0, 0.001, periods)),
        "high": price * (1 + np.random.normal(0.005, 0.005, periods)),
        "low": price * (1 + np.random.normal(-0.005, 0.005, periods)),
        "close": price,
        "volume": np.random.randint(1000, 10000, periods),
    }, index=dates)
    # Ensure high/low are consistent
    data["high"] = data[["open", "close", "high"]].max(axis=1)
    data["low"] = data[["open", "close", "low"]].min(axis=1)
    return data


def create_test_strategy(strategy_type: str = "momentum") -> BaseStrategy:
    """Create a test strategy instance."""
    if strategy_type == "momentum":
        return MomentumStrategy(
            params={
                "lookback": 20,
                "entry_threshold": 0.02,
                "exit_threshold": -0.01,
                "stop_loss": 0.05,
                "take_profit": 0.10,
            }
        )
    elif strategy_type == "mean_reversion":
        return MeanReversionStrategy(
            params={
                "lookback": 30,
                "entry_zscore": 2.0,
                "exit_zscore": 0.5,
                "stop_loss": 0.03,
            }
        )
    elif strategy_type == "breakout":
        return BreakoutStrategy(
            params={
                "lookback_high": 20,
                "lookback_low": 10,
                "breakout_multiplier": 1.02,
                "stop_loss": 0.04,
            }
        )
    elif strategy_type == "ensemble":
        return EnsembleStrategy(
            params={
                "strategies": ["momentum", "mean_reversion", "breakout"],
                "weights": [0.4, 0.3, 0.3],
                "voting": "weighted",
            }
        )
    else:
        return MomentumStrategy()


def create_engine_with_data(data: pd.DataFrame, strategy: BaseStrategy) -> BacktestEngine:
    """Create a backtest engine with given data and strategy."""
    return BacktestEngine(
        data=data,
        strategy=strategy,
        initial_capital=100000.0,
        commission=0.001,
        slippage=0.0005,
    )


# ----- Fixtures for different data sizes -----

@pytest.fixture(scope="function")
def small_data():
    """Small dataset: 1000 bars (~41 days of hourly data)."""
    start = datetime(2025, 1, 1)
    return generate_price_data(start, periods=1000, freq="1h")


@pytest.fixture(scope="function")
def medium_data():
    """Medium dataset: 5000 bars (~208 days)."""
    start = datetime(2024, 6, 1)
    return generate_price_data(start, periods=5000, freq="1h")


@pytest.fixture(scope="function")
def large_data():
    """Large dataset: 20000 bars (~833 days ~2.3 years)."""
    start = datetime(2023, 1, 1)
    return generate_price_data(start, periods=20000, freq="1h")


@pytest.fixture(scope="function")
def daily_data():
    """Daily data: 1000 days (~4 years)."""
    start = datetime(2020, 1, 1)
    return generate_price_data(start, periods=1000, freq="1D")


@pytest.fixture(scope="function")
def strategy_momentum():
    return create_test_strategy("momentum")


@pytest.fixture(scope="function")
def strategy_mean_reversion():
    return create_test_strategy("mean_reversion")


@pytest.fixture(scope="function")
def strategy_ensemble():
    return create_test_strategy("ensemble")


# ----- Benchmark tests -----

class TestBacktestExecution:
    """Benchmark backtest execution time."""

    @pytest.mark.parametrize(
        "data_fixture,strategy_fixture",
        [
            ("small_data", "strategy_momentum"),
            ("medium_data", "strategy_momentum"),
            ("large_data", "strategy_momentum"),
            ("daily_data", "strategy_momentum"),
            ("small_data", "strategy_mean_reversion"),
            ("medium_data", "strategy_mean_reversion"),
            ("small_data", "strategy_ensemble"),
            ("medium_data", "strategy_ensemble"),
        ],
    )
    def test_backtest_run(self, benchmark, request, data_fixture, strategy_fixture):
        """Benchmark running a backtest with different data sizes and strategies."""
        data = request.getfixturevalue(data_fixture)
        strategy = request.getfixturevalue(strategy_fixture)
        engine = create_engine_with_data(data, strategy)

        @benchmark
        def _run_backtest():
            result = engine.run()
            return result

        # The benchmark will measure the time. We can also assert result is not None.
        # We'll add a check that the benchmark ran successfully.
        assert _run_backtest is not None

    def test_backtest_with_metrics(self, benchmark, medium_data, strategy_momentum):
        """Benchmark backtest including metrics calculation."""
        engine = create_engine_with_data(medium_data, strategy_momentum)

        @benchmark
        def _run_with_metrics():
            result = engine.run()
            # Also compute metrics (should be done inside engine)
            # But if we want to explicitly measure metrics separately, we'll do a separate test.
            return result

    def test_backtest_with_transactions(self, benchmark, medium_data, strategy_momentum):
        """Benchmark backtest with transaction logging enabled."""
        engine = create_engine_with_data(medium_data, strategy_momentum)
        engine.enable_transaction_logging(True)

        @benchmark
        def _run_with_transactions():
            result = engine.run()
            return result


class TestMetricsCalculation:
    """Benchmark metrics calculation from trade logs."""

    @pytest.fixture
    def trade_logs(self, medium_data, strategy_momentum):
        """Pre-generate trade logs from a backtest."""
        engine = create_engine_with_data(medium_data, strategy_momentum)
        result = engine.run()
        return result.trades

    def test_metrics_calculation(self, benchmark, trade_logs):
        """Benchmark calculating all metrics from trade logs."""
        calculator = MetricsCalculator()

        @benchmark
        def _calc_metrics():
            metrics = calculator.calculate_all(trade_logs)
            return metrics

    def test_sharpe_calculation(self, benchmark, trade_logs):
        """Benchmark Sharpe ratio calculation."""
        calculator = MetricsCalculator()

        @benchmark
        def _calc_sharpe():
            return calculator.sharpe_ratio(trade_logs)

    def test_drawdown_calculation(self, benchmark, trade_logs):
        """Benchmark drawdown calculation."""
        calculator = MetricsCalculator()

        @benchmark
        def _calc_drawdown():
            return calculator.max_drawdown(trade_logs)

    def test_monte_carlo(self, benchmark, trade_logs):
        """Benchmark Monte Carlo simulation on trade logs."""
        simulator = MonteCarloSimulator()

        @benchmark
        def _run_monte_carlo():
            results = simulator.simulate(
                trades=trade_logs,
                num_simulations=1000,
                horizon=252,
            )
            return results

    def test_monte_carlo_large(self, benchmark, trade_logs):
        """Benchmark Monte Carlo with 5000 simulations."""
        simulator = MonteCarloSimulator()

        @benchmark
        def _run_large_monte_carlo():
            results = simulator.simulate(
                trades=trade_logs,
                num_simulations=5000,
                horizon=252,
            )
            return results


class TestStrategyOptimization:
    """Benchmark strategy parameter optimization."""

    @pytest.fixture
    def optimizer_data(self, medium_data):
        return medium_data

    def test_grid_search_optimization(self, benchmark, optimizer_data):
        """Benchmark grid search optimization."""
        strategy = MomentumStrategy()
        param_grid = {
            "lookback": [10, 20, 30, 50],
            "entry_threshold": [0.01, 0.02, 0.03],
            "exit_threshold": [-0.01, -0.005, -0.02],
            "stop_loss": [0.03, 0.05, 0.08],
        }
        optimizer = GridSearchOptimizer(
            data=optimizer_data,
            strategy_class=MomentumStrategy,
            param_grid=param_grid,
            metric="sharpe_ratio",
        )

        @benchmark
        def _grid_search():
            results = optimizer.optimize()
            return results

    def test_bayesian_optimization(self, benchmark, optimizer_data):
        """Benchmark Bayesian optimization."""
        strategy = MomentumStrategy()
        param_bounds = {
            "lookback": (5, 60),
            "entry_threshold": (0.005, 0.05),
            "exit_threshold": (-0.03, -0.001),
            "stop_loss": (0.01, 0.10),
        }
        optimizer = BayesianOptimizer(
            data=optimizer_data,
            strategy_class=MomentumStrategy,
            param_bounds=param_bounds,
            metric="sharpe_ratio",
            n_iter=20,
        )

        @benchmark
        def _bayesian_opt():
            results = optimizer.optimize()
            return results


class TestWalkForward:
    """Benchmark walk-forward analysis."""

    @pytest.fixture
    def walk_forward_data(self, large_data):
        return large_data

    def test_walk_forward_analysis(self, benchmark, walk_forward_data):
        """Benchmark walk-forward analysis with multiple windows."""
        analyzer = WalkForwardAnalyzer(
            data=walk_forward_data,
            strategy_class=MomentumStrategy,
            in_sample_days=180,
            out_sample_days=30,
            optimization_method="grid",
            param_grid={
                "lookback": [10, 20, 30],
                "entry_threshold": [0.01, 0.02],
                "stop_loss": [0.03, 0.05],
            },
        )

        @benchmark
        def _walk_forward():
            results = analyzer.run()
            return results

    def test_walk_forward_with_reoptimization(self, benchmark, walk_forward_data):
        """Benchmark walk-forward with re-optimization at each step."""
        analyzer = WalkForwardAnalyzer(
            data=walk_forward_data,
            strategy_class=MomentumStrategy,
            in_sample_days=90,
            out_sample_days=30,
            optimization_method="bayesian",
            param_bounds={
                "lookback": (5, 50),
                "entry_threshold": (0.005, 0.04),
                "stop_loss": (0.01, 0.08),
            },
            reoptimize=True,
        )

        @benchmark
        def _walk_forward_reopt():
            results = analyzer.run()
            return results


class TestDataProcessing:
    """Benchmark data preprocessing and feature engineering for backtest."""

    def test_technical_indicators(self, benchmark, large_data):
        """Benchmark computing all technical indicators."""
        from backend.ai.datasets.feature_engineering import FeatureEngineer

        engineer = FeatureEngineer()
        indicators = ["sma", "ema", "rsi", "macd", "bbands", "atr"]

        @benchmark
        def _compute_indicators():
            features = engineer.add_indicators(large_data, indicators)
            return features

    def test_multi_symbol_data(self, benchmark):
        """Benchmark backtest on multi-symbol data."""
        # Generate data for 5 symbols
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        data_dict = {}
        for sym in symbols:
            data_dict[sym] = generate_price_data(
                datetime(2024, 1, 1), periods=5000, freq="1h"
            )

        # Create a strategy that works on multiple symbols
        from backend.ai.strategies.portfolio_strategy import PortfolioStrategy

        strategy = PortfolioStrategy(
            symbols=symbols,
            allocation_method="equal",
            rebalance_freq=5,  # rebalance every 5 days
        )

        @benchmark
        def _multi_symbol_backtest():
            engine = BacktestEngine(
                data=data_dict,
                strategy=strategy,
                initial_capital=1000000.0,
            )
            result = engine.run()
            return result


# ----- Benchmark report generator -----

def test_generate_backtest_benchmark_report(perf_client):
    """
    Generate a report of backtest performance for different data sizes.
    This runs a series of backtests and records the times in a report.
    """
    sizes = [1000, 5000, 10000, 20000]
    strategies = ["momentum", "mean_reversion", "ensemble"]
    results = {}

    for size in sizes:
        data = generate_price_data(datetime(2024, 1, 1), periods=size, freq="1h")
        for strat_name in strategies:
            strategy = create_test_strategy(strat_name)
            engine = create_engine_with_data(data, strategy)
            start = time.perf_counter()
            result = engine.run()
            elapsed = time.perf_counter() - start
            results[f"{strat_name}_{size}"] = {
                "strategy": strat_name,
                "data_size": size,
                "elapsed": elapsed,
                "trades": len(result.trades),
                "final_equity": result.final_equity,
            }

    # Print report
    print("\n" + "=" * 60)
    print("BACKTEST PERFORMANCE BENCHMARK REPORT")
    print("=" * 60)
    for key, data in sorted(results.items()):
        print(f"{key:30s} {data['elapsed']:8.3f}s  trades: {data['trades']:4d}  equity: {data['final_equity']:10.0f}")
    print("=" * 60)

    # Save to file
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"backtest_perf_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }, f, indent=2)
    print(f"Report saved to {report_path}")
