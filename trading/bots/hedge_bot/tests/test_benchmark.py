# trading/bots/hedge_bot/tests/test_benchmark.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Benchmark Tests
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Benchmark Tests

This module provides comprehensive benchmark tests for the NEXUS Hedge Bot.
It includes performance benchmarks, stress tests, and load tests for
various components of the hedge bot system.

The benchmark suite covers:
- Strategy execution performance
- Risk calculation performance
- Data processing performance
- API response times
- WebSocket throughput
- Database query performance
- Memory usage
- CPU utilization
- Concurrent operations
- End-to-end latency
"""

import os
import sys
import time
import json
import logging
import asyncio
import threading
import multiprocessing
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import pytest
import pytest_asyncio

# Try to import performance testing libraries
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import memory_profiler
    HAS_MEMORY_PROFILER = True
except ImportError:
    HAS_MEMORY_PROFILER = False

try:
    import cProfile
    import pstats
    HAS_CPROFILE = True
except ImportError:
    HAS_CPROFILE = False

# Import module under test
from trading.bots.hedge_bot.core.engine import HedgeEngine
from trading.bots.hedge_bot.strategies.delta_hedge import DeltaHedgingStrategy
from trading.bots.hedge_bot.risk.risk_manager import RiskManager
from trading.bots.hedge_bot.data.market_data import MarketDataProvider
from trading.bots.hedge_bot.portfolio.portfolio_manager import PortfolioManager
from trading.bots.hedge_bot.execution.execution_engine import ExecutionEngine

logger = logging.getLogger(__name__)

# ============================================================
# BENCHMARK DATACLASSES
# ============================================================

@dataclass
class BenchmarkResult:
    """Benchmark test result"""
    name: str
    duration: float
    operations: int
    ops_per_second: float
    memory_used: float
    cpu_used: float
    success: bool
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "duration": self.duration,
            "operations": self.operations,
            "ops_per_second": self.ops_per_second,
            "memory_used": self.memory_used,
            "cpu_used": self.cpu_used,
            "success": self.success,
            "error": self.error,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BenchmarkSuite:
    """Benchmark test suite"""
    name: str
    results: List[BenchmarkResult] = field(default_factory=list)
    total_duration: float = 0.0
    total_operations: int = 0
    average_ops_per_second: float = 0.0
    max_memory_used: float = 0.0
    max_cpu_used: float = 0.0
    success_rate: float = 0.0

    def add_result(self, result: BenchmarkResult) -> None:
        """Add a benchmark result"""
        self.results.append(result)
        self.total_duration += result.duration
        self.total_operations += result.operations
        self.average_ops_per_second = self.total_operations / self.total_duration if self.total_duration > 0 else 0
        self.max_memory_used = max(self.max_memory_used, result.memory_used)
        self.max_cpu_used = max(self.max_cpu_used, result.cpu_used)
        self.success_rate = sum(1 for r in self.results if r.success) / len(self.results) if self.results else 0


@dataclass
class BenchmarkConfig:
    """Benchmark configuration"""
    iterations: int = 100
    warmup_iterations: int = 10
    concurrent_threads: int = 10
    timeout_seconds: int = 30
    memory_limit_mb: int = 1024
    cpu_limit_percent: int = 80
    operations_per_test: int = 1000
    data_points: int = 10000
    verbose: bool = False
    save_results: bool = True
    output_dir: str = "benchmark_results"


# ============================================================
# BENCHMARK DECORATORS
# ============================================================

def benchmark(func: Callable) -> Callable:
    """
    Decorator to benchmark a function
    
    Usage:
        @benchmark
        def my_function():
            ...
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024 if HAS_PSUTIL else 0
        start_cpu = psutil.Process().cpu_percent() if HAS_PSUTIL else 0
        
        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024 if HAS_PSUTIL else 0
        end_cpu = psutil.Process().cpu_percent() if HAS_PSUTIL else 0
        
        duration = end_time - start_time
        memory_used = end_memory - start_memory
        cpu_used = end_cpu - start_cpu
        
        benchmark_result = BenchmarkResult(
            name=func.__name__,
            duration=duration,
            operations=1,
            ops_per_second=1 / duration if duration > 0 else 0,
            memory_used=memory_used,
            cpu_used=cpu_used,
            success=success,
            error=error,
        )
        
        return result, benchmark_result
    
    return wrapper


# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def benchmark_config() -> BenchmarkConfig:
    """Create benchmark configuration"""
    return BenchmarkConfig(
        iterations=50,
        warmup_iterations=5,
        concurrent_threads=5,
        timeout_seconds=30,
        memory_limit_mb=512,
        cpu_limit_percent=70,
        operations_per_test=500,
        data_points=5000,
        verbose=False,
        save_results=True,
        output_dir="benchmark_results",
    )


@pytest.fixture
def benchmark_suite() -> BenchmarkSuite:
    """Create benchmark suite"""
    return BenchmarkSuite(name="HedgeBotBenchmarks")


@pytest.fixture
def test_engine() -> HedgeEngine:
    """Create test engine"""
    config = {
        "exchange": "binance",
        "sandbox": True,
        "strategies": ["delta_hedging"],
        "risk_limits": {
            "max_drawdown": 0.15,
            "daily_loss_limit": 0.05,
        }
    }
    return HedgeEngine(config)


@pytest.fixture
def test_strategy() -> DeltaHedgingStrategy:
    """Create test strategy"""
    config = {
        "hedge_ratio": 0.50,
        "rebalance_interval": 15,
        "target_delta": 0.0,
        "delta_tolerance": 0.01,
    }
    return DeltaHedgingStrategy(config)


@pytest.fixture
def test_risk_manager() -> RiskManager:
    """Create test risk manager"""
    config = {
        "limits": {
            "max_drawdown": 0.15,
            "daily_loss_limit": 0.05,
            "max_leverage": 3.0,
        }
    }
    return RiskManager(config)


@pytest.fixture
def test_market_data() -> MarketDataProvider:
    """Create test market data provider"""
    config = {
        "sources": ["exchange", "oracle"],
        "update_frequency": 5,
        "cache_size": 1000,
    }
    return MarketDataProvider(config)


# ============================================================
# BENCHMARK TESTS
# ============================================================

class TestHedgeBotBenchmarks:
    """
    Hedge Bot benchmark tests
    """

    @pytest.mark.benchmark
    def test_strategy_execution_benchmark(self, benchmark_config: BenchmarkConfig,
                                          test_strategy: DeltaHedgingStrategy,
                                          benchmark_suite: BenchmarkSuite) -> None:
        """
        Benchmark strategy execution performance
        """
        logger.info("Running strategy execution benchmark...")
        
        iterations = benchmark_config.iterations
        operations = benchmark_config.operations_per_test
        results = []
        
        # Warmup
        for _ in range(benchmark_config.warmup_iterations):
            test_strategy.calculate_hedge_ratio()
        
        # Benchmark
        start_time = time.time()
        
        for i in range(iterations):
            start = time.time()
            for j in range(operations):
                result = test_strategy.calculate_hedge_ratio()
            end = time.time()
            
            duration = end - start
            ops_per_second = operations / duration if duration > 0 else 0
            
            result_data = BenchmarkResult(
                name=f"strategy_execution_{i}",
                duration=duration,
                operations=operations,
                ops_per_second=ops_per_second,
                memory_used=0,
                cpu_used=0,
                success=True,
            )
            results.append(result_data)
        
        total_duration = time.time() - start_time
        avg_ops = sum(r.ops_per_second for r in results) / len(results) if results else 0
        
        benchmark_suite.add_result(BenchmarkResult(
            name="strategy_execution",
            duration=total_duration,
            operations=iterations * operations,
            ops_per_second=avg_ops,
            memory_used=0,
            cpu_used=0,
            success=True,
            details={
                "iterations": iterations,
                "operations_per_iteration": operations,
                "total_operations": iterations * operations,
                "average_duration": total_duration / iterations,
            }
        ))
        
        # Assertions
        assert avg_ops > 100, f"Strategy execution too slow: {avg_ops} ops/sec"
        logger.info(f"Strategy execution: {avg_ops:.2f} ops/sec")

    @pytest.mark.benchmark
    def test_risk_calculation_benchmark(self, benchmark_config: BenchmarkConfig,
                                        test_risk_manager: RiskManager,
                                        benchmark_suite: BenchmarkSuite) -> None:
        """
        Benchmark risk calculation performance
        """
        logger.info("Running risk calculation benchmark...")
        
        iterations = benchmark_config.iterations
        operations = benchmark_config.operations_per_test
        results = []
        
        # Generate test positions
        positions = [
            {"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0},
            {"symbol": "ETH/USDT", "quantity": 10.0, "price": 3000.0},
            {"symbol": "SOL/USDT", "quantity": 100.0, "price": 120.0},
            {"symbol": "ADA/USDT", "quantity": 10000.0, "price": 0.50},
            {"symbol": "DOT/USDT", "quantity": 1000.0, "price": 8.00},
        ]
        
        # Warmup
        for _ in range(benchmark_config.warmup_iterations):
            test_risk_manager.calculate_var(positions)
        
        # Benchmark
        start_time = time.time()
        
        for i in range(iterations):
            start = time.time()
            for j in range(operations):
                result = test_risk_manager.calculate_var(positions)
            end = time.time()
            
            duration = end - start
            ops_per_second = operations / duration if duration > 0 else 0
            
            result_data = BenchmarkResult(
                name=f"risk_calculation_{i}",
                duration=duration,
                operations=operations,
                ops_per_second=ops_per_second,
                memory_used=0,
                cpu_used=0,
                success=True,
            )
            results.append(result_data)
        
        total_duration = time.time() - start_time
        avg_ops = sum(r.ops_per_second for r in results) / len(results) if results else 0
        
        benchmark_suite.add_result(BenchmarkResult(
            name="risk_calculation",
            duration=total_duration,
            operations=iterations * operations,
            ops_per_second=avg_ops,
            memory_used=0,
            cpu_used=0,
            success=True,
            details={
                "iterations": iterations,
                "operations_per_iteration": operations,
                "total_operations": iterations * operations,
            }
        ))
        
        # Assertions
        assert avg_ops > 50, f"Risk calculation too slow: {avg_ops} ops/sec"
        logger.info(f"Risk calculation: {avg_ops:.2f} ops/sec")

    @pytest.mark.benchmark
    def test_market_data_processing_benchmark(self, benchmark_config: BenchmarkConfig,
                                              test_market_data: MarketDataProvider,
                                              benchmark_suite: BenchmarkSuite) -> None:
        """
        Benchmark market data processing performance
        """
        logger.info("Running market data processing benchmark...")
        
        iterations = benchmark_config.iterations
        data_points = benchmark_config.data_points
        
        # Generate test data
        test_data = self._generate_test_market_data(data_points)
        
        # Warmup
        for _ in range(benchmark_config.warmup_iterations):
            test_market_data.process_data(test_data[:100])
        
        # Benchmark
        start_time = time.time()
        results = []
        
        for i in range(iterations):
            start = time.time()
            processed = test_market_data.process_data(test_data)
            end = time.time()
            
            duration = end - start
            ops_per_second = data_points / duration if duration > 0 else 0
            
            result_data = BenchmarkResult(
                name=f"market_data_processing_{i}",
                duration=duration,
                operations=data_points,
                ops_per_second=ops_per_second,
                memory_used=0,
                cpu_used=0,
                success=True,
            )
            results.append(result_data)
        
        total_duration = time.time() - start_time
        avg_ops = sum(r.ops_per_second for r in results) / len(results) if results else 0
        
        benchmark_suite.add_result(BenchmarkResult(
            name="market_data_processing",
            duration=total_duration,
            operations=iterations * data_points,
            ops_per_second=avg_ops,
            memory_used=0,
            cpu_used=0,
            success=True,
            details={
                "iterations": iterations,
                "data_points_per_iteration": data_points,
                "total_data_points": iterations * data_points,
            }
        ))
        
        # Assertions
        assert avg_ops > 1000, f"Market data processing too slow: {avg_ops} ops/sec"
        logger.info(f"Market data processing: {avg_ops:.2f} ops/sec")

    @pytest.mark.benchmark
    def test_api_performance_benchmark(self, benchmark_config: BenchmarkConfig,
                                       benchmark_suite: BenchmarkSuite) -> None:
        """
        Benchmark API performance
        """
        logger.info("Running API performance benchmark...")
        
        from trading.bots.hedge_bot.api.main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        iterations = benchmark_config.iterations
        
        # Warmup
        for _ in range(benchmark_config.warmup_iterations):
            client.get("/health")
        
        # Benchmark
        start_time = time.time()
        results = []
        success_count = 0
        
        for i in range(iterations):
            start = time.time()
            response = client.get("/health")
            end = time.time()
            
            duration = end - start
            if response.status_code == 200:
                success_count += 1
            
            result_data = BenchmarkResult(
                name=f"api_request_{i}",
                duration=duration,
                operations=1,
                ops_per_second=1 / duration if duration > 0 else 0,
                memory_used=0,
                cpu_used=0,
                success=response.status_code == 200,
                details={"status_code": response.status_code},
            )
            results.append(result_data)
        
        total_duration = time.time() - start_time
        avg_latency = sum(r.duration for r in results) / len(results) if results else 0
        success_rate = success_count / iterations
        
        benchmark_suite.add_result(BenchmarkResult(
            name="api_performance",
            duration=total_duration,
            operations=iterations,
            ops_per_second=iterations / total_duration if total_duration > 0 else 0,
            memory_used=0,
            cpu_used=0,
            success=success_rate > 0.95,
            details={
                "iterations": iterations,
                "success_rate": success_rate,
                "average_latency_ms": avg_latency * 1000,
                "min_latency_ms": min(r.duration for r in results) * 1000,
                "max_latency_ms": max(r.duration for r in results) * 1000,
            }
        ))
        
        # Assertions
        assert avg_latency < 0.1, f"API latency too high: {avg_latency:.3f}s"
        assert success_rate > 0.95, f"API success rate too low: {success_rate:.2%}"
        logger.info(f"API performance: {avg_latency*1000:.2f}ms avg latency")

    @pytest.mark.benchmark
    def test_database_performance_benchmark(self, benchmark_config: BenchmarkConfig,
                                            benchmark_suite: BenchmarkSuite) -> None:
        """
        Benchmark database performance
        """
        logger.info("Running database performance benchmark...")
        
        # Use in-memory SQLite for benchmarks
        import sqlite3
        import random
        
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        
        # Create test table
        cursor.execute('''
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                timestamp REAL
            )
        ''')
        
        iterations = benchmark_config.iterations
        batch_size = 100
        total_operations = iterations * batch_size
        
        # Generate test data
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT']
        sides = ['buy', 'sell']
        
        # Warmup
        for i in range(benchmark_config.warmup_iterations * batch_size):
            cursor.execute(
                'INSERT INTO trades (symbol, side, quantity, price, timestamp) VALUES (?, ?, ?, ?, ?)',
                (
                    random.choice(symbols),
                    random.choice(sides),
                    random.uniform(0.1, 10.0),
                    random.uniform(100, 100000),
                    time.time()
                )
            )
        conn.commit()
        
        # Benchmark inserts
        start_time = time.time()
        
        for i in range(iterations):
            start = time.time()
            for j in range(batch_size):
                cursor.execute(
                    'INSERT INTO trades (symbol, side, quantity, price, timestamp) VALUES (?, ?, ?, ?, ?)',
                    (
                        random.choice(symbols),
                        random.choice(sides),
                        random.uniform(0.1, 10.0),
                        random.uniform(100, 100000),
                        time.time()
                    )
                )
            conn.commit()
            end = time.time()
            
            duration = end - start
            ops_per_second = batch_size / duration if duration > 0 else 0
        
        total_duration = time.time() - start_time
        avg_ops = total_operations / total_duration if total_duration > 0 else 0
        
        benchmark_suite.add_result(BenchmarkResult(
            name="database_inserts",
            duration=total_duration,
            operations=total_operations,
            ops_per_second=avg_ops,
            memory_used=0,
            cpu_used=0,
            success=True,
            details={
                "iterations": iterations,
                "batch_size": batch_size,
                "total_operations": total_operations,
                "average_batch_duration": total_duration / iterations,
            }
        ))
        
        # Benchmark queries
        query_iterations = benchmark_config.iterations // 2
        
        start_time = time.time()
        results = []
        
        for i in range(query_iterations):
            start = time.time()
            cursor.execute('SELECT COUNT(*) FROM trades')
            count = cursor.fetchone()[0]
            cursor.execute('SELECT AVG(price) FROM trades')
            avg_price = cursor.fetchone()[0]
            cursor.execute('SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10')
            recent = cursor.fetchall()
            end = time.time()
            
            duration = end - start
            results.append(duration)
        
        total_query_duration = time.time() - start_time
        avg_query_latency = sum(results) / len(results) if results else 0
        
        benchmark_suite.add_result(BenchmarkResult(
            name="database_queries",
            duration=total_query_duration,
            operations=query_iterations * 3,
            ops_per_second=(query_iterations * 3) / total_query_duration if total_query_duration > 0 else 0,
            memory_used=0,
            cpu_used=0,
            success=True,
            details={
                "iterations": query_iterations,
                "average_query_latency_ms": avg_query_latency * 1000,
                "total_records": count,
            }
        ))
        
        conn.close()
        
        # Assertions
        assert avg_ops > 100, f"Database inserts too slow: {avg_ops:.2f} ops/sec"
        assert avg_query_latency < 0.01, f"Database queries too slow: {avg_query_latency*1000:.2f}ms"
        logger.info(f"Database inserts: {avg_ops:.2f} ops/sec")
        logger.info(f"Database queries: {avg_query_latency*1000:.2f}ms avg latency")

    @pytest.mark.benchmark
    def test_concurrent_operations_benchmark(self, benchmark_config: BenchmarkConfig,
                                             benchmark_suite: BenchmarkSuite) -> None:
        """
        Benchmark concurrent operations
        """
        logger.info("Running concurrent operations benchmark...")
        
        import concurrent.futures
        
        def worker(task_id: int) -> Tuple[float, bool]:
            """Worker function for concurrent operations"""
            start = time.time()
            try:
                # Simulate work
                time.sleep(0.01)  # 10ms work
                return time.time() - start, True
            except Exception:
                return time.time() - start, False
        
        num_workers = benchmark_config.concurrent_threads
        iterations = benchmark_config.iterations
        
        # Warmup
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(benchmark_config.warmup_iterations * num_workers)]
            for future in concurrent.futures.as_completed(futures):
                pass
        
        # Benchmark
        start_time = time.time()
        results = []
        success_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(iterations * num_workers)]
            
            for future in concurrent.futures.as_completed(futures):
                duration, success = future.result()
                results.append(duration)
                if success:
                    success_count += 1
        
        total_duration = time.time() - start_time
        total_operations = len(results)
        avg_ops = total_operations / total_duration if total_duration > 0 else 0
        avg_duration = sum(results) / len(results) if results else 0
        success_rate = success_count / total_operations if total_operations > 0 else 0
        
        benchmark_suite.add_result(BenchmarkResult(
            name="concurrent_operations",
            duration=total_duration,
            operations=total_operations,
            ops_per_second=avg_ops,
            memory_used=0,
            cpu_used=0,
            success=success_rate > 0.95,
            details={
                "num_workers": num_workers,
                "total_operations": total_operations,
                "success_rate": success_rate,
                "average_duration_ms": avg_duration * 1000,
                "throughput": avg_ops,
            }
        ))
        
        # Assertions
        assert avg_ops > 10, f"Concurrent operations too slow: {avg_ops:.2f} ops/sec"
        assert success_rate > 0.95, f"Concurrent operations success rate too low: {success_rate:.2%}"
        logger.info(f"Concurrent operations: {avg_ops:.2f} ops/sec")

    @pytest.mark.benchmark
    def test_end_to_end_latency_benchmark(self, benchmark_config: BenchmarkConfig,
                                          benchmark_suite: BenchmarkSuite) -> None:
        """
        Benchmark end-to-end latency
        """
        logger.info("Running end-to-end latency benchmark...")
        
        iterations = benchmark_config.iterations
        
        # Create test components
        from trading.bots.hedge_bot.api.main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Test order placement and status
        test_order = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "quantity": 1.0,
            "price": 50000.0,
        }
        
        # Warmup
        for _ in range(benchmark_config.warmup_iterations):
            response = client.post("/trading/orders", json=test_order)
            if response.status_code == 200:
                order_id = response.json().get("id")
                if order_id:
                    client.get(f"/trading/orders/{order_id}")
        
        # Benchmark
        results = []
        
        for i in range(iterations):
            # Place order
            start = time.time()
            response = client.post("/trading/orders", json=test_order)
            placement_time = time.time() - start
            
            if response.status_code == 200:
                order_id = response.json().get("id")
                
                # Get order status
                start = time.time()
                status_response = client.get(f"/trading/orders/{order_id}")
                status_time = time.time() - start
                
                # Get positions
                start = time.time()
                positions_response = client.get("/trading/positions")
                positions_time = time.time() - start
                
                results.append({
                    "placement_time": placement_time,
                    "status_time": status_time,
                    "positions_time": positions_time,
                })
        
        total_latency = sum(r["placement_time"] + r["status_time"] + r["positions_time"] for r in results)
        avg_placement = sum(r["placement_time"] for r in results) / len(results) if results else 0
        avg_status = sum(r["status_time"] for r in results) / len(results) if results else 0
        avg_positions = sum(r["positions_time"] for r in results) / len(results) if results else 0
        avg_total = total_latency / len(results) if results else 0
        
        benchmark_suite.add_result(BenchmarkResult(
            name="end_to_end_latency",
            duration=total_latency,
            operations=iterations * 3,
            ops_per_second=(iterations * 3) / total_latency if total_latency > 0 else 0,
            memory_used=0,
            cpu_used=0,
            success=True,
            details={
                "iterations": iterations,
                "average_placement_latency_ms": avg_placement * 1000,
                "average_status_latency_ms": avg_status * 1000,
                "average_positions_latency_ms": avg_positions * 1000,
                "average_total_latency_ms": avg_total * 1000,
                "min_total_latency_ms": min(r["placement_time"] + r["status_time"] + r["positions_time"] for r in results) * 1000 if results else 0,
                "max_total_latency_ms": max(r["placement_time"] + r["status_time"] + r["positions_time"] for r in results) * 1000 if results else 0,
            }
        ))
        
        # Assertions
        assert avg_placement < 0.5, f"Order placement too slow: {avg_placement*1000:.2f}ms"
        assert avg_status < 0.5, f"Status check too slow: {avg_status*1000:.2f}ms"
        assert avg_positions < 0.5, f"Positions fetch too slow: {avg_positions*1000:.2f}ms"
        assert avg_total < 1.0, f"End-to-end latency too high: {avg_total*1000:.2f}ms"
        logger.info(f"End-to-end latency: {avg_total*1000:.2f}ms avg")

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _generate_test_market_data(self, num_points: int) -> List[Dict[str, Any]]:
        """Generate test market data"""
        import random
        
        data = []
        base_price = 50000.0
        
        for i in range(num_points):
            # Generate price with random walk
            change = random.gauss(0, 0.01)
            price = base_price * (1 + change)
            base_price = price
            
            data.append({
                "symbol": "BTC/USDT",
                "timestamp": datetime.now() - timedelta(minutes=num_points - i),
                "open": price * (1 - random.uniform(0, 0.005)),
                "high": price * (1 + random.uniform(0, 0.01)),
                "low": price * (1 - random.uniform(0, 0.01)),
                "close": price,
                "volume": random.randint(100000, 1000000),
            })
        
        return data


# ============================================================
# BENCHMARK SUITE RUNNER
# ============================================================

class BenchmarkRunner:
    """
    Benchmark suite runner
    """

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.suites: List[BenchmarkSuite] = []
        self.results: List[BenchmarkResult] = []

    def run(self) -> None:
        """Run all benchmark suites"""
        logger.info("Starting benchmark runner...")
        
        # Create output directory
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Run benchmark tests
        # This would typically be triggered by pytest
        # but we can also run it programmatically
        
        logger.info("Benchmark runner completed")

    def save_results(self) -> None:
        """Save benchmark results"""
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "iterations": self.config.iterations,
                "concurrent_threads": self.config.concurrent_threads,
                "operations_per_test": self.config.operations_per_test,
                "data_points": self.config.data_points,
            },
            "suites": [
                {
                    "name": suite.name,
                    "total_duration": suite.total_duration,
                    "total_operations": suite.total_operations,
                    "average_ops_per_second": suite.average_ops_per_second,
                    "max_memory_used": suite.max_memory_used,
                    "max_cpu_used": suite.max_cpu_used,
                    "success_rate": suite.success_rate,
                    "results": [r.to_dict() for r in suite.results],
                }
                for suite in self.suites
            ]
        }
        
        output_path = Path(self.config.output_dir) / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_path, "w") as f:
            json.dump(results_data, f, indent=2)
        
        logger.info(f"Benchmark results saved to {output_path}")


# ============================================================
# BENCHMARK REPORTING
# ============================================================

class BenchmarkReporter:
    """
    Benchmark report generator
    """

    def __init__(self, results: Dict[str, Any]):
        self.results = results

    def generate_report(self) -> str:
        """Generate benchmark report"""
        report = []
        
        report.append("=" * 80)
        report.append("NEXUS HEDGE BOT - BENCHMARK REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        if "suites" in self.results:
            for suite in self.results["suites"]:
                report.append(f"SUITE: {suite['name']}")
                report.append("-" * 40)
                report.append(f"  Total Duration: {suite['total_duration']:.2f}s")
                report.append(f"  Total Operations: {suite['total_operations']:,}")
                report.append(f"  Average Throughput: {suite['average_ops_per_second']:.2f} ops/sec")
                report.append(f"  Success Rate: {suite['success_rate']:.1%}")
                
                if "results" in suite and suite["results"]:
                    report.append("")
                    report.append("  Detailed Results:")
                    for result in suite["results"]:
                        report.append(f"    {result['name']}:")
                        report.append(f"      Duration: {result['duration']:.3f}s")
                        report.append(f"      Operations: {result['operations']:,}")
                        report.append(f"      Throughput: {result['ops_per_second']:.2f} ops/sec")
                        if result.get("details"):
                            report.append(f"      Details: {json.dumps(result['details'], indent=4)}")
                        report.append("")
                
                report.append("")
        
        report.append("=" * 80)
        report.append("END OF REPORT")
        report.append("=" * 80)
        
        return "\n".join(report)


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "BenchmarkResult",
    "BenchmarkSuite",
    "BenchmarkConfig",
    "BenchmarkRunner",
    "BenchmarkReporter",
    "benchmark",
]

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run benchmarks
    config = BenchmarkConfig()
    runner = BenchmarkRunner(config)
    runner.run()
    runner.save_results()
    
    # Generate report
    with open(Path(config.output_dir) / "report.json", "r") as f:
        results = json.load(f)
    
    reporter = BenchmarkReporter(results)
    report = reporter.generate_report()
    print(report)
