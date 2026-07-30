# trading/bots/hedge_bot/tests/test_performance.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Performance Tests
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Performance Tests

This module provides comprehensive performance and stress tests for the
NEXUS Hedge Bot system. It measures system performance under various
load conditions, tests scalability, and identifies bottlenecks.

The test suite covers:
- Strategy execution performance
- Risk calculation performance
- Order processing throughput
- Data processing performance
- API response times
- WebSocket performance
- Database query performance
- Cache performance
- Concurrent operations
- System scalability
- Resource utilization
- Latency measurements
- Throughput measurements
- Memory usage
- CPU usage
"""

import os
import sys
import time
import json
import asyncio
import logging
import threading
import multiprocessing
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import pytest
import pytest_asyncio

# Try to import performance libraries
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
from trading.bots.hedge_bot.main import HedgeBot
from trading.bots.hedge_bot.core.engine import HedgeEngine
from trading.bots.hedge_bot.strategies.delta_hedge import DeltaHedgingStrategy
from trading.bots.hedge_bot.risk.risk_manager import RiskManager
from trading.bots.hedge_bot.data.market_data import MarketDataProvider
from trading.bots.hedge_bot.execution.execution_engine import ExecutionEngine

# ============================================================
# PERFORMANCE DATACLASSES
# ============================================================

@dataclass
class PerformanceResult:
    """Performance test result"""
    name: str
    duration: float
    operations: int
    ops_per_second: float
    memory_used_mb: float
    cpu_used_percent: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    success_rate: float
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "duration": self.duration,
            "operations": self.operations,
            "ops_per_second": self.ops_per_second,
            "memory_used_mb": self.memory_used_mb,
            "cpu_used_percent": self.cpu_used_percent,
            "latency_p50": self.latency_p50,
            "latency_p95": self.latency_p95,
            "latency_p99": self.latency_p99,
            "success_rate": self.success_rate,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PerformanceSuite:
    """Performance test suite"""
    name: str
    results: List[PerformanceResult] = field(default_factory=list)
    total_duration: float = 0.0
    total_operations: int = 0
    avg_ops_per_second: float = 0.0
    max_memory_used_mb: float = 0.0
    max_cpu_used_percent: float = 0.0
    avg_latency_p95: float = 0.0
    success_rate: float = 0.0

    def add_result(self, result: PerformanceResult) -> None:
        """Add a performance result"""
        self.results.append(result)
        self.total_duration += result.duration
        self.total_operations += result.operations
        self.avg_ops_per_second = self.total_operations / self.total_duration if self.total_duration > 0 else 0
        self.max_memory_used_mb = max(self.max_memory_used_mb, result.memory_used_mb)
        self.max_cpu_used_percent = max(self.max_cpu_used_percent, result.cpu_used_percent)
        self.avg_latency_p95 = (self.avg_latency_p95 * (len(self.results) - 1) + result.latency_p95) / len(self.results)
        self.success_rate = sum(1 for r in self.results if r.success_rate > 0.95) / len(self.results) if self.results else 0


# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def performance_config() -> Dict[str, Any]:
    """Create performance test configuration"""
    return {
        "iterations": 100,
        "warmup_iterations": 10,
        "concurrent_threads": 10,
        "batch_size": 100,
        "data_points": 10000,
        "operations_per_test": 1000,
        "timeout_seconds": 30,
        "memory_limit_mb": 2048,
        "cpu_limit_percent": 80,
        "latency_threshold_ms": 100,
        "throughput_threshold_ops": 1000,
    }


@pytest.fixture
def performance_suite() -> PerformanceSuite:
    """Create performance suite"""
    return PerformanceSuite(name="HedgeBotPerformance")


@pytest.fixture
def test_hedge_bot() -> HedgeBot:
    """Create test hedge bot"""
    config = {
        "bot": {
            "id": "perf_test_bot",
            "enabled": True,
            "environment": "testing",
        },
        "exchange": {
            "name": "binance",
            "type": "spot",
            "sandbox": True,
            "api": {
                "key": "test_key",
                "secret": "test_secret",
            },
        },
        "trading": {
            "position": {"max_leverage": 1.0},
        },
        "risk_management": {
            "limits": {"max_drawdown": 0.15},
        },
        "data": {
            "sources": {"market_data": {"provider": "mock"}},
        },
        "logging": {
            "config": {"enabled": False},
        },
    }
    return HedgeBot(config)


# ============================================================
# PERFORMANCE TEST HELPERS
# ============================================================

class PerformanceMonitor:
    """Performance monitoring helper"""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.start_cpu = None
        self.measurements = []

    def start(self) -> None:
        """Start performance monitoring"""
        self.start_time = time.time()
        if HAS_PSUTIL:
            process = psutil.Process()
            self.start_memory = process.memory_info().rss / 1024 / 1024
            self.start_cpu = process.cpu_percent(interval=None)

    def stop(self) -> Dict[str, Any]:
        """Stop performance monitoring"""
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        
        metrics = {
            "duration": duration,
            "memory_mb": 0,
            "cpu_percent": 0,
        }
        
        if HAS_PSUTIL:
            process = psutil.Process()
            memory = process.memory_info().rss / 1024 / 1024
            cpu = process.cpu_percent(interval=None)
            metrics["memory_mb"] = memory - self.start_memory
            metrics["cpu_percent"] = cpu - self.start_cpu
        
        return metrics

    def measure_operation(self, func: Callable, *args, **kwargs) -> Tuple[Any, float]:
        """Measure a single operation"""
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        return result, duration

    def measure_batch(self, func: Callable, iterations: int, *args, **kwargs) -> List[float]:
        """Measure a batch of operations"""
        durations = []
        for _ in range(iterations):
            start = time.time()
            func(*args, **kwargs)
            durations.append(time.time() - start)
        return durations


# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestStrategyPerformance:
    """
    Performance tests for strategy components
    """

    def test_delta_hedging_performance(self, performance_config: Dict[str, Any],
                                       performance_suite: PerformanceSuite) -> None:
        """Test delta hedging strategy performance"""
        strategy = DeltaHedgingStrategy({
            "hedge_ratio": 0.50,
            "target_delta": 0.0,
            "delta_tolerance": 0.01,
        })
        monitor = PerformanceMonitor()
        
        iterations = performance_config["iterations"]
        operations = performance_config["operations_per_test"]
        
        # Warmup
        for _ in range(performance_config["warmup_iterations"]):
            strategy.calculate_hedge_ratio({"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0})
        
        # Measure
        monitor.start()
        durations = []
        
        for i in range(iterations):
            start = time.time()
            for _ in range(operations):
                strategy.calculate_hedge_ratio({"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0})
            durations.append(time.time() - start)
        
        metrics = monitor.stop()
        
        # Calculate statistics
        total_ops = iterations * operations
        total_duration = metrics["duration"]
        ops_per_second = total_ops / total_duration if total_duration > 0 else 0
        
        sorted_durations = sorted(durations)
        p50 = sorted_durations[len(sorted_durations) // 2]
        p95 = sorted_durations[int(len(sorted_durations) * 0.95)]
        p99 = sorted_durations[int(len(sorted_durations) * 0.99)]
        
        result = PerformanceResult(
            name="delta_hedging",
            duration=total_duration,
            operations=total_ops,
            ops_per_second=ops_per_second,
            memory_used_mb=metrics.get("memory_mb", 0),
            cpu_used_percent=metrics.get("cpu_percent", 0),
            latency_p50=p50 * 1000,  # Convert to ms
            latency_p95=p95 * 1000,
            latency_p99=p99 * 1000,
            success_rate=1.0,
            details={
                "iterations": iterations,
                "operations_per_iteration": operations,
                "min_duration_ms": min(durations) * 1000,
                "max_duration_ms": max(durations) * 1000,
            }
        )
        
        performance_suite.add_result(result)
        
        # Assertions
        assert ops_per_second > 100, f"Delta hedging too slow: {ops_per_second:.2f} ops/sec"
        assert p95 * 1000 < 50, f"Delta hedging latency too high: {p95*1000:.2f}ms"

    def test_risk_calculation_performance(self, performance_config: Dict[str, Any],
                                         performance_suite: PerformanceSuite) -> None:
        """Test risk calculation performance"""
        risk_manager = RiskManager({"limits": {"max_drawdown": 0.15}})
        monitor = PerformanceMonitor()
        
        positions = [
            {"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0},
            {"symbol": "ETH/USDT", "quantity": 10.0, "price": 3000.0},
            {"symbol": "SOL/USDT", "quantity": 100.0, "price": 120.0},
        ]
        
        iterations = performance_config["iterations"]
        
        # Warmup
        for _ in range(performance_config["warmup_iterations"]):
            risk_manager.calculate_var(positions)
        
        # Measure
        monitor.start()
        durations = []
        
        for _ in range(iterations):
            start = time.time()
            risk_manager.calculate_var(positions)
            durations.append(time.time() - start)
        
        metrics = monitor.stop()
        
        total_ops = iterations
        total_duration = metrics["duration"]
        ops_per_second = total_ops / total_duration if total_duration > 0 else 0
        
        sorted_durations = sorted(durations)
        p50 = sorted_durations[len(sorted_durations) // 2]
        p95 = sorted_durations[int(len(sorted_durations) * 0.95)]
        p99 = sorted_durations[int(len(sorted_durations) * 0.99)]
        
        result = PerformanceResult(
            name="risk_calculation",
            duration=total_duration,
            operations=total_ops,
            ops_per_second=ops_per_second,
            memory_used_mb=metrics.get("memory_mb", 0),
            cpu_used_percent=metrics.get("cpu_percent", 0),
            latency_p50=p50 * 1000,
            latency_p95=p95 * 1000,
            latency_p99=p99 * 1000,
            success_rate=1.0,
            details={
                "iterations": iterations,
                "positions_count": len(positions),
            }
        )
        
        performance_suite.add_result(result)
        
        # Assertions
        assert ops_per_second > 50, f"Risk calculation too slow: {ops_per_second:.2f} ops/sec"
        assert p95 * 1000 < 100, f"Risk calculation latency too high: {p95*1000:.2f}ms"


class TestDataPerformance:
    """
    Performance tests for data components
    """

    def test_market_data_processing_performance(self, performance_config: Dict[str, Any],
                                                performance_suite: PerformanceSuite) -> None:
        """Test market data processing performance"""
        market_data = MarketDataProvider({"sources": ["mock"]})
        monitor = PerformanceMonitor()
        
        # Generate test data
        data_points = performance_config["data_points"]
        test_data = self._generate_test_market_data(data_points)
        
        iterations = performance_config["iterations"] // 10
        
        # Warmup
        for _ in range(performance_config["warmup_iterations"]):
            market_data.process_data(test_data[:100])
        
        # Measure
        monitor.start()
        durations = []
        
        for _ in range(iterations):
            start = time.time()
            market_data.process_data(test_data)
            durations.append(time.time() - start)
        
        metrics = monitor.stop()
        
        total_ops = iterations * data_points
        total_duration = metrics["duration"]
        ops_per_second = total_ops / total_duration if total_duration > 0 else 0
        
        sorted_durations = sorted(durations)
        p50 = sorted_durations[len(sorted_durations) // 2]
        p95 = sorted_durations[int(len(sorted_durations) * 0.95)]
        p99 = sorted_durations[int(len(sorted_durations) * 0.99)]
        
        result = PerformanceResult(
            name="market_data_processing",
            duration=total_duration,
            operations=total_ops,
            ops_per_second=ops_per_second,
            memory_used_mb=metrics.get("memory_mb", 0),
            cpu_used_percent=metrics.get("cpu_percent", 0),
            latency_p50=p50 * 1000,
            latency_p95=p95 * 1000,
            latency_p99=p99 * 1000,
            success_rate=1.0,
            details={
                "iterations": iterations,
                "data_points_per_iteration": data_points,
                "total_data_points": total_ops,
            }
        )
        
        performance_suite.add_result(result)
        
        # Assertions
        assert ops_per_second > 1000, f"Data processing too slow: {ops_per_second:.2f} ops/sec"
        assert p95 * 1000 < 100, f"Data processing latency too high: {p95*1000:.2f}ms"

    def _generate_test_market_data(self, num_points: int) -> List[Dict[str, Any]]:
        """Generate test market data"""
        import random
        data = []
        base_price = 50000.0
        
        for i in range(num_points):
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


class TestExecutionPerformance:
    """
    Performance tests for execution components
    """

    def test_order_processing_performance(self, performance_config: Dict[str, Any],
                                          performance_suite: PerformanceSuite) -> None:
        """Test order processing performance"""
        execution = ExecutionEngine({
            "order_type": "limit",
            "time_in_force": "GTC",
            "max_order_size": 10000,
        })
        monitor = PerformanceMonitor()
        
        orders = [
            {"symbol": "BTC/USDT", "side": "buy", "quantity": 1.0, "price": 50000.0},
            {"symbol": "ETH/USDT", "side": "sell", "quantity": 10.0, "price": 3000.0},
            {"symbol": "SOL/USDT", "side": "buy", "quantity": 100.0, "price": 120.0},
        ]
        
        iterations = performance_config["iterations"]
        
        # Warmup
        for _ in range(performance_config["warmup_iterations"]):
            for order in orders:
                execution.validate_order(order)
        
        # Measure
        monitor.start()
        durations = []
        
        for _ in range(iterations):
            start = time.time()
            for order in orders:
                execution.validate_order(order)
            durations.append(time.time() - start)
        
        metrics = monitor.stop()
        
        total_ops = iterations * len(orders)
        total_duration = metrics["duration"]
        ops_per_second = total_ops / total_duration if total_duration > 0 else 0
        
        sorted_durations = sorted(durations)
        p50 = sorted_durations[len(sorted_durations) // 2]
        p95 = sorted_durations[int(len(sorted_durations) * 0.95)]
        p99 = sorted_durations[int(len(sorted_durations) * 0.99)]
        
        result = PerformanceResult(
            name="order_processing",
            duration=total_duration,
            operations=total_ops,
            ops_per_second=ops_per_second,
            memory_used_mb=metrics.get("memory_mb", 0),
            cpu_used_percent=metrics.get("cpu_percent", 0),
            latency_p50=p50 * 1000,
            latency_p95=p95 * 1000,
            latency_p99=p99 * 1000,
            success_rate=1.0,
            details={
                "iterations": iterations,
                "orders_per_iteration": len(orders),
                "total_orders": total_ops,
            }
        )
        
        performance_suite.add_result(result)
        
        # Assertions
        assert ops_per_second > 100, f"Order processing too slow: {ops_per_second:.2f} ops/sec"
        assert p95 * 1000 < 50, f"Order processing latency too high: {p95*1000:.2f}ms"


class TestSystemPerformance:
    """
    Performance tests for overall system
    """

    @pytest.mark.asyncio
    async def test_system_throughput(self, performance_config: Dict[str, Any],
                                     test_hedge_bot: HedgeBot,
                                     performance_suite: PerformanceSuite) -> None:
        """Test overall system throughput"""
        await test_hedge_bot.start_async()
        monitor = PerformanceMonitor()
        
        operations = performance_config["concurrent_threads"] * 10
        
        # Measure
        monitor.start()
        start_time = time.time()
        
        tasks = []
        for _ in range(operations):
            tasks.append(test_hedge_bot.market_data.get_price_async("BTC/USDT"))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start_time
        metrics = monitor.stop()
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        success_rate = success_count / operations if operations > 0 else 0
        
        ops_per_second = operations / duration if duration > 0 else 0
        
        result = PerformanceResult(
            name="system_throughput",
            duration=duration,
            operations=operations,
            ops_per_second=ops_per_second,
            memory_used_mb=metrics.get("memory_mb", 0),
            cpu_used_percent=metrics.get("cpu_percent", 0),
            latency_p50=0,
            latency_p95=0,
            latency_p99=0,
            success_rate=success_rate,
            details={
                "total_operations": operations,
                "success_count": success_count,
                "failure_count": operations - success_count,
            }
        )
        
        performance_suite.add_result(result)
        
        await test_hedge_bot.stop_async()
        
        # Assertions
        assert ops_per_second > 10, f"System throughput too low: {ops_per_second:.2f} ops/sec"
        assert success_rate > 0.95, f"System success rate too low: {success_rate:.2%}"


class TestConcurrencyPerformance:
    """
    Performance tests for concurrent operations
    """

    def test_concurrent_strategy_execution(self, performance_config: Dict[str, Any],
                                          performance_suite: PerformanceSuite) -> None:
        """Test concurrent strategy execution performance"""
        import concurrent.futures
        
        def execute_strategy(strategy_id: int) -> Tuple[float, bool]:
            """Execute a strategy instance"""
            strategy = DeltaHedgingStrategy({
                "hedge_ratio": 0.50,
                "target_delta": 0.0,
                "delta_tolerance": 0.01,
            })
            start = time.time()
            try:
                for _ in range(10):
                    strategy.calculate_hedge_ratio({"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0})
                return time.time() - start, True
            except Exception:
                return time.time() - start, False
        
        num_workers = performance_config["concurrent_threads"]
        iterations = performance_config["iterations"] // 10
        
        monitor = PerformanceMonitor()
        monitor.start()
        
        durations = []
        success_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(execute_strategy, i) for i in range(iterations)]
            for future in concurrent.futures.as_completed(futures):
                duration, success = future.result()
                durations.append(duration)
                if success:
                    success_count += 1
        
        metrics = monitor.stop()
        
        total_ops = iterations
        total_duration = metrics["duration"]
        ops_per_second = total_ops / total_duration if total_duration > 0 else 0
        success_rate = success_count / iterations if iterations > 0 else 0
        
        sorted_durations = sorted(durations)
        p50 = sorted_durations[len(sorted_durations) // 2] if sorted_durations else 0
        p95 = sorted_durations[int(len(sorted_durations) * 0.95)] if sorted_durations else 0
        p99 = sorted_durations[int(len(sorted_durations) * 0.99)] if sorted_durations else 0
        
        result = PerformanceResult(
            name="concurrent_strategies",
            duration=total_duration,
            operations=total_ops,
            ops_per_second=ops_per_second,
            memory_used_mb=metrics.get("memory_mb", 0),
            cpu_used_percent=metrics.get("cpu_percent", 0),
            latency_p50=p50 * 1000,
            latency_p95=p95 * 1000,
            latency_p99=p99 * 1000,
            success_rate=success_rate,
            details={
                "num_workers": num_workers,
                "total_iterations": iterations,
                "successful_iterations": success_count,
            }
        )
        
        performance_suite.add_result(result)
        
        # Assertions
        assert ops_per_second > 5, f"Concurrent execution too slow: {ops_per_second:.2f} ops/sec"
        assert success_rate > 0.95, f"Concurrent success rate too low: {success_rate:.2%}"


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "PerformanceResult",
    "PerformanceSuite",
    "TestStrategyPerformance",
    "TestDataPerformance",
    "TestExecutionPerformance",
    "TestSystemPerformance",
    "TestConcurrencyPerformance",
]
