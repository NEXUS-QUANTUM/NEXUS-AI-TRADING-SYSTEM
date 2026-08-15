"""
Swing Bot Benchmark Tests
==========================

This module contains benchmark tests for the Swing Bot trading system.
"""

import pytest
import time
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import statistics

from trading.bots.swing_bot.core import Engine
from trading.bots.swing_bot.strategies import MomentumStrategy, MeanReversionStrategy
from trading.bots.swing_bot.bots.sniper_bot import SniperBot
from trading.bots.swing_bot.risk_management import RiskManager
from trading.bots.swing_bot.execution_engine import ExecutionEngine
from trading.bots.swing_bot.monitoring import MonitoringService

from .fixtures import get_config_fixture


class BenchmarkRunner:
    """Utility class for running benchmarks."""
    
    def __init__(self):
        self.results = {}
    
    def run_benchmark(self, name: str, func, *args, **kwargs):
        """Run a benchmark and record results."""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        
        self.results[name] = {
            "result": result,
            "elapsed": elapsed,
            "timestamp": datetime.now().isoformat()
        }
        
        return result, elapsed
    
    def get_report(self):
        """Generate a benchmark report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "benchmarks": self.results,
            "summary": {
                "total_benchmarks": len(self.results),
                "avg_time": statistics.mean([r["elapsed"] for r in self.results.values()]),
                "max_time": max([r["elapsed"] for r in self.results.values()]),
                "min_time": min([r["elapsed"] for r in self.results.values()])
            }
        }
        return report
    
    def save_report(self, filepath: Path):
        """Save benchmark report to file."""
        report = self.get_report()
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)


class TestBenchmarks:
    """Benchmark tests for the Swing Bot."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def benchmark_runner(self):
        """Create a benchmark runner."""
        return BenchmarkRunner()
    
    @pytest.fixture
    def large_market_data(self):
        """Create large market data for benchmarking."""
        n_rows = 100000
        np.random.seed(42)
        dates = [datetime.now() + timedelta(milliseconds=i) for i in range(n_rows)]
        return pd.DataFrame({
            'timestamp': dates,
            'open': np.random.randn(n_rows) * 5 + 100,
            'high': np.random.randn(n_rows) * 5 + 102,
            'low': np.random.randn(n_rows) * 5 + 98,
            'close': np.random.randn(n_rows) * 5 + 100,
            'volume': np.random.randint(100000, 1000000, n_rows)
        })
    
    def test_strategy_benchmark(self, benchmark_runner, large_market_data):
        """Benchmark strategy performance."""
        strategy = MomentumStrategy()
        
        # Run benchmark
        result, elapsed = benchmark_runner.run_benchmark(
            "momentum_strategy",
            strategy.generate_signals,
            large_market_data
        )
        
        assert result is not None
        assert elapsed < 5.0  # Should complete in less than 5 seconds
        print(f"Momentum Strategy Benchmark: {elapsed:.2f}s")
    
    def test_strategy_comparison_benchmark(self, benchmark_runner, large_market_data):
        """Benchmark multiple strategies for comparison."""
        strategies = {
            "momentum": MomentumStrategy(),
            "mean_reversion": MeanReversionStrategy()
        }
        
        for name, strategy in strategies.items():
            result, elapsed = benchmark_runner.run_benchmark(
                f"{name}_strategy",
                strategy.generate_signals,
                large_market_data
            )
            
            assert result is not None
            print(f"{name.capitalize()} Strategy Benchmark: {elapsed:.2f}s")
    
    @pytest.mark.asyncio
    async def test_bot_benchmark(self, benchmark_runner, config, large_market_data):
        """Benchmark bot performance."""
        risk_manager = RiskManager(config=config)
        execution_engine = ExecutionEngine(config=config)
        
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        bot.start()
        
        # Run benchmark
        result, elapsed = await benchmark_runner.run_benchmark(
            "sniper_bot_processing",
            bot.process_market_data,
            large_market_data
        )
        
        bot.stop()
        
        assert result is not None
        assert elapsed < 10.0  # Should complete in less than 10 seconds
        print(f"Sniper Bot Benchmark: {elapsed:.2f}s")
    
    @pytest.mark.asyncio
    async def test_async_throughput_benchmark(self, benchmark_runner, config):
        """Benchmark async throughput."""
        risk_manager = RiskManager(config=config)
        execution_engine = ExecutionEngine(config=config)
        
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        bot.start()
        
        # Generate test data
        n_batches = 10
        batch_size = 1000
        
        async def process_batch():
            df = pd.DataFrame({
                'timestamp': [datetime.now() + timedelta(seconds=i) for i in range(batch_size)],
                'open': np.random.randn(batch_size) * 5 + 100,
                'high': np.random.randn(batch_size) * 5 + 102,
                'low': np.random.randn(batch_size) * 5 + 98,
                'close': np.random.randn(batch_size) * 5 + 100,
                'volume': np.random.randint(100000, 1000000, batch_size)
            })
            return await bot.process_market_data(df)
        
        # Run benchmark
        start = time.perf_counter()
        tasks = [process_batch() for _ in range(n_batches)]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        
        benchmark_runner.results["async_throughput"] = {
            "result": len(results),
            "elapsed": elapsed,
            "batches": n_batches,
            "batch_size": batch_size,
            "total_processed": n_batches * batch_size,
            "throughput": (n_batches * batch_size) / elapsed
        }
        
        bot.stop()
        
        assert len(results) == n_batches
        print(f"Async Throughput Benchmark: {elapsed:.2f}s for {n_batches * batch_size} rows")
        print(f"Throughput: {(n_batches * batch_size) / elapsed:.0f} rows/second")
    
    def test_memory_benchmark(self, benchmark_runner, large_market_data):
        """Benchmark memory usage."""
        import tracemalloc
        
        tracemalloc.start()
        
        strategy = MomentumStrategy()
        signals = strategy.generate_signals(large_market_data)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        benchmark_runner.results["memory_usage"] = {
            "current_mb": current / 1024 / 1024,
            "peak_mb": peak / 1024 / 1024,
            "signals_count": len(signals),
            "data_rows": len(large_market_data)
        }
        
        assert current < 200 * 1024 * 1024  # Less than 200 MB
        print(f"Memory Benchmark: {current / 1024 / 1024:.2f} MB current, {peak / 1024 / 1024:.2f} MB peak")
    
    def test_data_loading_benchmark(self, benchmark_runner, large_market_data):
        """Benchmark data loading and processing."""
        # Save data to temporary file
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            start = time.perf_counter()
            large_market_data.to_csv(f.name, index=False)
            write_time = time.perf_counter() - start
            
            start = time.perf_counter()
            df = pd.read_csv(f.name)
            read_time = time.perf_counter() - start
        
        os.unlink(f.name)
        
        benchmark_runner.results["data_loading"] = {
            "write_time": write_time,
            "read_time": read_time,
            "rows": len(large_market_data)
        }
        
        assert write_time < 1.0
        assert read_time < 1.0
        print(f"Data Loading Benchmark: Write {write_time:.2f}s, Read {read_time:.2f}s")
    
    def test_monitoring_benchmark(self, benchmark_runner, config):
        """Benchmark monitoring performance."""
        monitoring = MonitoringService(config=config)
        monitoring.start()
        
        # Generate many metrics
        start = time.perf_counter()
        for i in range(10000):
            monitoring.track_metric(f"test_metric_{i % 100}", i)
        elapsed = time.perf_counter() - start
        
        monitoring.stop()
        
        benchmark_runner.results["monitoring"] = {
            "metrics_count": 10000,
            "elapsed": elapsed,
            "throughput": 10000 / elapsed
        }
        
        assert elapsed < 1.0
        print(f"Monitoring Benchmark: {elapsed:.2f}s for 10000 metrics")
    
    def test_engine_benchmark(self, benchmark_runner, config, large_market_data):
        """Benchmark engine performance."""
        engine = Engine(config=config)
        
        # Register multiple strategies
        strategies = [
            MomentumStrategy(),
            MeanReversionStrategy()
        ]
        for strategy in strategies:
            engine.register_strategy(strategy)
        
        engine.start()
        
        # Run benchmark
        result, elapsed = benchmark_runner.run_benchmark(
            "engine_processing",
            engine.process_data,
            large_market_data
        )
        
        engine.stop()
        
        assert result is not None
        assert elapsed < 10.0
        print(f"Engine Benchmark: {elapsed:.2f}s")
    
    @pytest.mark.asyncio
    async def test_concurrent_benchmark(self, benchmark_runner, config):
        """Benchmark concurrent operations."""
        risk_manager = RiskManager(config=config)
        execution_engine = ExecutionEngine(config=config)
        
        # Create multiple bots
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
        bots = []
        
        for symbol in symbols:
            bot = SniperBot(
                config=config,
                risk_manager=risk_manager,
                execution_engine=execution_engine,
                symbol=symbol
            )
            bot.start()
            bots.append(bot)
        
        # Generate test data
        df = pd.DataFrame({
            'timestamp': [datetime.now() + timedelta(seconds=i) for i in range(1000)],
            'open': np.random.randn(1000) * 5 + 100,
            'high': np.random.randn(1000) * 5 + 102,
            'low': np.random.randn(1000) * 5 + 98,
            'close': np.random.randn(1000) * 5 + 100,
            'volume': np.random.randint(100000, 1000000, 1000)
        })
        
        # Run concurrent processing
        start = time.perf_counter()
        tasks = [bot.process_market_data(df) for bot in bots]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        
        # Stop bots
        for bot in bots:
            bot.stop()
        
        benchmark_runner.results["concurrent"] = {
            "bots_count": len(bots),
            "symbols": symbols,
            "elapsed": elapsed,
            "results_count": len(results)
        }
        
        assert len(results) == len(symbols)
        print(f"Concurrent Benchmark: {elapsed:.2f}s for {len(symbols)} bots")


class TestPerformanceBenchmarks:
    """Performance benchmarks with reporting."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def benchmark_runner(self):
        """Create a benchmark runner."""
        return BenchmarkRunner()
    
    @pytest.fixture
    def large_market_data(self):
        """Create large market data for benchmarking."""
        n_rows = 100000
        np.random.seed(42)
        dates = [datetime.now() + timedelta(milliseconds=i) for i in range(n_rows)]
        return pd.DataFrame({
            'timestamp': dates,
            'open': np.random.randn(n_rows) * 5 + 100,
            'high': np.random.randn(n_rows) * 5 + 102,
            'low': np.random.randn(n_rows) * 5 + 98,
            'close': np.random.randn(n_rows) * 5 + 100,
            'volume': np.random.randint(100000, 1000000, n_rows)
        })
    
    def test_full_system_benchmark(self, benchmark_runner, config, large_market_data):
        """Test full system benchmark."""
        # Create all components
        risk_manager = RiskManager(config=config)
        execution_engine = ExecutionEngine(config=config)
        monitoring = MonitoringService(config=config)
        
        # Start monitoring
        monitoring.start()
        
        # Create bot
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        # Run benchmark
        start = time.perf_counter()
        bot.start()
        
        # Process data
        result = bot.process_market_data(large_market_data)
        bot.stop()
        
        elapsed = time.perf_counter() - start
        
        # Stop monitoring
        monitoring.stop()
        
        benchmark_runner.results["full_system"] = {
            "elapsed": elapsed,
            "data_rows": len(large_market_data),
            "result": bool(result)
        }
        
        print(f"Full System Benchmark: {elapsed:.2f}s")
    
    @pytest.mark.asyncio
    async def test_stress_benchmark(self, benchmark_runner, config):
        """Stress test benchmark."""
        risk_manager = RiskManager(config=config)
        execution_engine = ExecutionEngine(config=config)
        
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        bot.start()
        
        # Generate many small batches
        n_batches = 100
        batch_size = 100
        
        def generate_batch():
            return pd.DataFrame({
                'timestamp': [datetime.now() + timedelta(seconds=i) for i in range(batch_size)],
                'open': np.random.randn(batch_size) * 5 + 100,
                'high': np.random.randn(batch_size) * 5 + 102,
                'low': np.random.randn(batch_size) * 5 + 98,
                'close': np.random.randn(batch_size) * 5 + 100,
                'volume': np.random.randint(100000, 1000000, batch_size)
            })
        
        # Process batches
        start = time.perf_counter()
        for i in range(n_batches):
            df = generate_batch()
            await bot.process_market_data(df)
        elapsed = time.perf_counter() - start
        
        bot.stop()
        
        benchmark_runner.results["stress"] = {
            "batches": n_batches,
            "batch_size": batch_size,
            "total_processed": n_batches * batch_size,
            "elapsed": elapsed,
            "avg_time_per_batch": elapsed / n_batches
        }
        
        print(f"Stress Benchmark: {elapsed:.2f}s for {n_batches * batch_size} rows")
    
    def test_benchmark_report(self, benchmark_runner, tmp_path):
        """Test benchmark report generation."""
        # Add some benchmark results
        benchmark_runner.results["test"] = {
            "result": True,
            "elapsed": 0.123,
            "timestamp": datetime.now().isoformat()
        }
        
        # Generate report
        report = benchmark_runner.get_report()
        assert "benchmarks" in report
        assert "summary" in report
        
        # Save report
        report_path = tmp_path / "benchmark_report.json"
        benchmark_runner.save_report(report_path)
        assert report_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
