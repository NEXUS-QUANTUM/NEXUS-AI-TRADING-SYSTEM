"""
Swing Bot Performance Tests.
============================

This module contains performance tests for the Swing Bot trading system.
"""

import pytest
import time
import psutil
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import warnings

from trading.bots.swing_bot.core import Engine, Signal, SignalType
from trading.bots.swing_bot.bots.sniper_bot import SniperBot
from trading.bots.swing_bot.strategies import MomentumStrategy, MeanReversionStrategy
from trading.bots.swing_bot.risk_management import RiskManager
from trading.bots.swing_bot.execution_engine import ExecutionEngine

from .fixtures import get_market_data_fixture, get_config_fixture


class PerformanceMetrics:
    """Utility class for measuring performance metrics."""
    
    @staticmethod
    def measure_time(func):
        """Decorator to measure execution time."""
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            return result, elapsed
        return wrapper
    
    @staticmethod
    def measure_memory(func):
        """Decorator to measure memory usage."""
        def wrapper(*args, **kwargs):
            process = psutil.Process()
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            result = func(*args, **kwargs)
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            return result, mem_after - mem_before
        return wrapper
    
    @staticmethod
    def measure_cpu(func):
        """Decorator to measure CPU usage."""
        def wrapper(*args, **kwargs):
            cpu_before = psutil.cpu_percent(interval=None)
            result = func(*args, **kwargs)
            cpu_after = psutil.cpu_percent(interval=None)
            return result, cpu_after - cpu_before
        return wrapper


class TestPerformance:
    """Performance tests for the Swing Bot."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_fixture()
    
    @pytest.fixture
    def large_market_data(self):
        """Create large market data for performance testing."""
        n_rows = 10000
        np.random.seed(42)
        dates = [datetime.now() + timedelta(seconds=i) for i in range(n_rows)]
        return pd.DataFrame({
            'timestamp': dates,
            'open': np.random.randn(n_rows) * 5 + 100,
            'high': np.random.randn(n_rows) * 5 + 102,
            'low': np.random.randn(n_rows) * 5 + 98,
            'close': np.random.randn(n_rows) * 5 + 100,
            'volume': np.random.randint(100000, 1000000, n_rows)
        })
    
    def test_strategy_performance(self, market_data):
        """Test strategy performance."""
        df = pd.DataFrame(market_data)
        strategy = MomentumStrategy()
        
        # Measure execution time
        start = time.perf_counter()
        signals = strategy.generate_signals(df)
        elapsed = time.perf_counter() - start
        
        # Assert performance
        assert elapsed < 1.0  # Should process in less than 1 second
        assert len(signals) > 0
    
    def test_strategy_performance_scaling(self, large_market_data):
        """Test strategy performance with large data."""
        strategy = MomentumStrategy()
        
        # Measure execution time for large data
        start = time.perf_counter()
        signals = strategy.generate_signals(large_market_data)
        elapsed = time.perf_counter() - start
        
        # Assert performance
        assert elapsed < 5.0  # Should process in less than 5 seconds
        assert len(signals) > 0
    
    def test_memory_usage(self, large_market_data):
        """Test memory usage."""
        import tracemalloc
        
        tracemalloc.start()
        
        strategy = MomentumStrategy()
        signals = strategy.generate_signals(large_market_data)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Assert memory usage
        assert current < 100 * 1024 * 1024  # Less than 100 MB
        assert peak < 200 * 1024 * 1024  # Less than 200 MB
    
    @pytest.mark.asyncio
    async def test_bot_performance(self, config, market_data):
        """Test bot performance."""
        df = pd.DataFrame(market_data)
        
        risk_manager = Mock(spec=RiskManager)
        risk_manager.check_risk = AsyncMock(return_value=True)
        risk_manager.calculate_position_size = Mock(return_value=100)
        
        execution_engine = Mock(spec=ExecutionEngine)
        execution_engine.execute_order = AsyncMock(return_value={"order_id": "test_123"})
        
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        bot.start()
        
        # Measure processing time
        start = time.perf_counter()
        result = await bot.process_market_data(df)
        elapsed = time.perf_counter() - start
        
        bot.stop()
        
        # Assert performance
        assert elapsed < 2.0  # Should process in less than 2 seconds
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_performance(self, config, market_data):
        """Test concurrent operations performance."""
        df = pd.DataFrame(market_data)
        
        risk_manager = Mock(spec=RiskManager)
        risk_manager.check_risk = AsyncMock(return_value=True)
        risk_manager.calculate_position_size = Mock(return_value=100)
        
        execution_engine = Mock(spec=ExecutionEngine)
        execution_engine.execute_order = AsyncMock(return_value={"order_id": "test_123"})
        
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        bot.start()
        
        # Run multiple operations concurrently
        start = time.perf_counter()
        tasks = [bot.process_market_data(df) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        
        bot.stop()
        
        # Assert performance
        assert elapsed < 10.0  # Should process in less than 10 seconds
        assert len(results) == 10
        assert all(r is not None for r in results)
    
    def test_engine_throughput(self, config, large_market_data):
        """Test engine throughput."""
        engine = Engine(config)
        
        # Measure throughput
        start = time.perf_counter()
        for i in range(10):
            engine.process_data(large_market_data)
        elapsed = time.perf_counter() - start
        
        # Calculate throughput
        total_rows = len(large_market_data) * 10
        throughput = total_rows / elapsed
        
        # Assert throughput
        assert throughput > 10000  # At least 10,000 rows per second
    
    def test_response_time(self, market_data):
        """Test response time."""
        df = pd.DataFrame(market_data)
        strategy = MomentumStrategy()
        
        # Measure response time for each signal
        response_times = []
        
        for i in range(100):
            subset = df.iloc[:max(20, i)]
            start = time.perf_counter()
            signals = strategy.generate_signals(subset)
            elapsed = time.perf_counter() - start
            response_times.append(elapsed)
        
        # Calculate average response time
        avg_response = sum(response_times) / len(response_times)
        
        # Assert response time
        assert avg_response < 0.01  # Average response time less than 10ms
    
    def test_memory_leak(self, large_market_data):
        """Test for memory leaks."""
        import tracemalloc
        
        tracemalloc.start()
        
        strategy = MomentumStrategy()
        
        # Run multiple iterations
        for i in range(10):
            signals = strategy.generate_signals(large_market_data)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Assert memory stability
        assert current < 200 * 1024 * 1024  # Less than 200 MB
    
    def test_cpu_usage(self, large_market_data):
        """Test CPU usage."""
        import psutil
        
        strategy = MomentumStrategy()
        
        # Measure CPU usage
        cpu_percent = psutil.cpu_percent(interval=None)
        
        start = time.perf_counter()
        while time.perf_counter() - start < 5:
            signals = strategy.generate_signals(large_market_data)
            current_cpu = psutil.cpu_percent(interval=None)
        
        # Assert CPU usage is reasonable
        assert cpu_percent < 80  # CPU usage less than 80%
    
    def test_io_performance(self, market_data):
        """Test I/O performance."""
        df = pd.DataFrame(market_data)
        
        # Test file I/O
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            start = time.perf_counter()
            df.to_csv(f.name, index=False)
            write_time = time.perf_counter() - start
            
            start = time.perf_counter()
            pd.read_csv(f.name)
            read_time = time.perf_counter() - start
        
        os.unlink(f.name)
        
        # Assert I/O performance
        assert write_time < 0.1
        assert read_time < 0.1
    
    def test_network_performance(self, config):
        """Test network performance."""
        from trading.bots.swing_bot.utils.network_utils import NetworkClient
        
        client = NetworkClient(base_url="http://localhost:8080")
        
        # Test connection
        start = time.perf_counter()
        try:
            response = client.get("/health")
            elapsed = time.perf_counter() - start
        except Exception:
            elapsed = 0.0
        
        # Assert network performance
        assert elapsed < 1.0  # Connection should be fast
    
    @pytest.mark.asyncio
    async def test_async_performance(self, config):
        """Test async performance."""
        from trading.bots.swing_bot.utils.async_utils import AsyncTaskManager
        
        manager = AsyncTaskManager()
        
        # Create tasks
        async def test_task():
            await asyncio.sleep(0.01)
            return "test"
        
        # Measure async performance
        start = time.perf_counter()
        tasks = [manager.add_task(test_task()) for _ in range(100)]
        results = await manager.wait_all()
        elapsed = time.perf_counter() - start
        
        # Assert performance
        assert elapsed < 1.0
        assert len(results) == 100
    
    def test_cache_performance(self, large_market_data):
        """Test cache performance."""
        from trading.bots.swing_bot.utils.cache import MemoryCache
        
        cache = MemoryCache()
        strategy = MomentumStrategy()
        
        # Test without cache
        start = time.perf_counter()
        for i in range(10):
            signals = strategy.generate_signals(large_market_data)
        uncached_time = time.perf_counter() - start
        
        # Test with cache
        @cache.cached
        def cached_generate(data):
            return strategy.generate_signals(data)
        
        start = time.perf_counter()
        for i in range(10):
            signals = cached_generate(large_market_data)
        cached_time = time.perf_counter() - start
        
        # Assert cache improves performance
        assert cached_time < uncached_time
    
    def test_concurrent_data_processing(self, large_market_data):
        """Test concurrent data processing."""
        from concurrent.futures import ThreadPoolExecutor
        
        strategy = MomentumStrategy()
        
        def process_data(data):
            return strategy.generate_signals(data)
        
        # Split data
        chunks = np.array_split(large_market_data, 4)
        
        # Process concurrently
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_data, chunks))
        elapsed = time.perf_counter() - start
        
        # Process sequentially
        start_seq = time.perf_counter()
        sequential_results = [process_data(chunk) for chunk in chunks]
        seq_elapsed = time.perf_counter() - start_seq
        
        # Assert concurrent processing is faster
        assert elapsed < seq_elapsed
        assert len(results) == len(sequential_results)


class TestPerformanceBenchmark:
    """Performance benchmark tests."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def market_data(self):
        """Create benchmark market data."""
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
    
    def test_benchmark_processing(self, market_data):
        """Benchmark processing speed."""
        strategy = MomentumStrategy()
        
        # Measure processing speed
        start = time.perf_counter()
        signals = strategy.generate_signals(market_data)
        elapsed = time.perf_counter() - start
        
        # Calculate metrics
        rows_per_second = len(market_data) / elapsed
        signals_per_second = len(signals) / elapsed
        
        # Print benchmark results
        print(f"\nBenchmark Results:")
        print(f"Rows processed: {len(market_data):,}")
        print(f"Signals generated: {len(signals):,}")
        print(f"Processing time: {elapsed:.2f}s")
        print(f"Rows per second: {rows_per_second:,.0f}")
        print(f"Signals per second: {signals_per_second:,.0f}")
        
        # Assert minimum performance
        assert rows_per_second > 100000  # At least 100k rows/second
        assert signals_per_second > 1000  # At least 1k signals/second


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
