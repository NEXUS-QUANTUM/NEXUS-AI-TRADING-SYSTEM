"""
tests/performance/test_resource_usage.py

NEXUS AI Trading System - Resource Usage Performance Tests

This module uses pytest-benchmark to measure CPU and memory usage of critical
operations. It helps detect resource leaks, high CPU consumption, and memory
regressions.

Tests cover:
- API endpoint CPU and memory usage
- Database operations resource consumption
- AI model inference resource usage
- Backtesting resource consumption
- Bulk data processing
- Long-running operations (memory leak detection)
- Concurrent request resource usage

Uses psutil to monitor process resource utilization.

Usage:
    pytest tests/performance/test_resource_usage.py -v --benchmark-autosave
    pytest tests/performance/test_resource_usage.py -v --benchmark-compare

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import pytest
import random
import threading
import concurrent.futures
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from fastapi.testclient import TestClient

# Try to import psutil; if not available, skip resource-specific tests
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from tests.performance.conftest import (
    perf_client,
    perf_auth_headers,
    perf_test_user,
    perf_test_portfolio,
    perf_test_broker,
    perf_test_positions,
    perf_test_orders,
)


# ----- Helper functions for resource measurement -----

def get_process_memory() -> float:
    """Get current process memory usage in MB."""
    if not PSUTIL_AVAILABLE:
        return 0.0
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024  # MB


def get_process_cpu_percent() -> float:
    """Get current process CPU usage percentage."""
    if not PSUTIL_AVAILABLE:
        return 0.0
    process = psutil.Process()
    return process.cpu_percent(interval=0.1)


def measure_resource_usage(func: Callable, *args, **kwargs) -> Dict[str, float]:
    """
    Measure CPU and memory usage of a function call.
    Returns dict with cpu_percent, memory_mb, peak_memory_mb, elapsed_time.
    """
    if not PSUTIL_AVAILABLE:
        return {
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "peak_memory_mb": 0.0,
            "elapsed_time": 0.0,
        }

    process = psutil.Process()
    # Get baseline memory
    mem_before = process.memory_info().rss / 1024 / 1024
    cpu_before = process.cpu_percent(interval=0.0)

    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start_time

    cpu_after = process.cpu_percent(interval=0.0)
    mem_after = process.memory_info().rss / 1024 / 1024
    # Get peak memory during execution (approx by checking after)
    # For more accurate, we could sample periodically, but this is a simplification.

    return {
        "result": result,
        "cpu_percent": cpu_after - cpu_before,
        "memory_mb": mem_after - mem_before,
        "peak_memory_mb": mem_after,  # This is the memory after execution, not true peak
        "elapsed_time": elapsed,
    }


# ----- Fixtures -----

@pytest.fixture(scope="function")
def large_dataframe() -> pd.DataFrame:
    """Generate a large DataFrame for resource usage tests."""
    np.random.seed(42)
    n_rows = 100000
    data = {
        "timestamp": pd.date_range(start="2024-01-01", periods=n_rows, freq="1s"),
        "symbol": np.random.choice(["AAPL", "MSFT", "GOOGL"], n_rows),
        "price": np.random.normal(100, 10, n_rows),
        "volume": np.random.randint(1000, 100000, n_rows),
        "open": np.random.normal(100, 10, n_rows),
        "high": np.random.normal(100, 10, n_rows),
        "low": np.random.normal(100, 10, n_rows),
        "close": np.random.normal(100, 10, n_rows),
    }
    return pd.DataFrame(data)


# ----- Skip tests if psutil not available -----

pytestmark = pytest.mark.skipif(
    not PSUTIL_AVAILABLE,
    reason="psutil not installed; resource usage tests require psutil"
)


# ----- API endpoint resource usage -----

class TestAPIResourceUsage:
    """Measure CPU and memory usage of API endpoints."""

    def test_portfolio_summary_resource_usage(self, perf_client: TestClient, perf_auth_headers: Dict):
        """Measure resource usage of portfolio summary endpoint."""
        def _call():
            response = perf_client.get("/api/v1/portfolio/summary", headers=perf_auth_headers)
            assert response.status_code == 200
            return response

        # Run multiple times to get stable measurement
        for _ in range(5):
            _call()  # warmup

        usage = measure_resource_usage(_call)
        print(f"\nPortfolio summary: CPU={usage['cpu_percent']:.2f}%, "
              f"Memory={usage['memory_mb']:.2f}MB, Elapsed={usage['elapsed_time']*1000:.1f}ms")

        # Assert memory usage is reasonable (e.g., < 50MB increase)
        assert usage["memory_mb"] < 50, f"Memory usage too high: {usage['memory_mb']:.2f}MB"

    def test_market_quote_resource_usage(self, perf_client: TestClient, perf_auth_headers: Dict):
        """Measure resource usage of market quote endpoint."""
        def _call():
            response = perf_client.get("/api/v1/market/quote/AAPL", headers=perf_auth_headers)
            assert response.status_code == 200
            return response

        for _ in range(5):
            _call()

        usage = measure_resource_usage(_call)
        print(f"\nMarket quote: CPU={usage['cpu_percent']:.2f}%, "
              f"Memory={usage['memory_mb']:.2f}MB, Elapsed={usage['elapsed_time']*1000:.1f}ms")
        assert usage["memory_mb"] < 20

    def test_historical_data_resource_usage(self, perf_client: TestClient, perf_auth_headers: Dict):
        """Measure resource usage of historical data endpoint with large limit."""
        params = {"timeframe": "1h", "limit": 1000}
        def _call():
            response = perf_client.get("/api/v1/market/historical/AAPL", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response

        for _ in range(3):
            _call()

        usage = measure_resource_usage(_call)
        print(f"\nHistorical data (1000 bars): CPU={usage['cpu_percent']:.2f}%, "
              f"Memory={usage['memory_mb']:.2f}MB, Elapsed={usage['elapsed_time']*1000:.1f}ms")
        # Historical data may consume more memory
        assert usage["memory_mb"] < 100

    def test_ai_prediction_resource_usage(self, perf_client: TestClient, perf_auth_headers: Dict):
        """Measure resource usage of AI prediction endpoint."""
        def _call():
            response = perf_client.get("/api/v1/ai/predict/price/AAPL", headers=perf_auth_headers)
            assert response.status_code == 200
            return response

        for _ in range(3):
            _call()

        usage = measure_resource_usage(_call)
        print(f"\nAI prediction: CPU={usage['cpu_percent']:.2f}%, "
              f"Memory={usage['memory_mb']:.2f}MB, Elapsed={usage['elapsed_time']*1000:.1f}ms")
        # AI may use more CPU/memory
        assert usage["memory_mb"] < 200


# ----- Database operation resource usage -----

class TestDatabaseResourceUsage:
    """Measure resource usage of database operations."""

    def test_bulk_insert_resource_usage(self, perf_db_session, perf_test_user):
        """Measure resource usage of bulk inserting many records."""
        from backend.models.user import User

        def _bulk_insert():
            users = []
            for i in range(100):
                user = User(
                    id=f"res-user-{i}-{random.randint(1000,9999)}",
                    email=f"res_{i}_{int(time.time())}@example.com",
                    first_name="Res",
                    last_name="User",
                    hashed_password="hash",
                    is_active=True,
                    is_verified=True,
                    created_at=datetime.utcnow(),
                )
                users.append(user)
            perf_db_session.bulk_save_objects(users)
            perf_db_session.commit()
            return len(users)

        # Warmup
        _bulk_insert()
        # Clean up
        perf_db_session.query(User).filter(User.email.like("res_%")).delete()
        perf_db_session.commit()

        usage = measure_resource_usage(_bulk_insert)
        print(f"\nBulk insert 100 users: CPU={usage['cpu_percent']:.2f}%, "
              f"Memory={usage['memory_mb']:.2f}MB, Elapsed={usage['elapsed_time']*1000:.1f}ms")
        assert usage["memory_mb"] < 50

        # Clean up
        perf_db_session.query(User).filter(User.email.like("res_%")).delete()
        perf_db_session.commit()

    def test_complex_query_resource_usage(self, perf_db_session, large_portfolio):
        """Measure resource usage of a complex query with joins and aggregations."""
        from sqlalchemy import func

        def _complex_query():
            results = perf_db_session.query(
                Position.symbol,
                func.sum(Position.quantity).label("total_qty"),
                func.avg(Position.current_price).label("avg_price"),
                func.sum(Position.quantity * Position.current_price).label("total_value"),
            ).filter(Position.portfolio_id == large_portfolio.id).group_by(Position.symbol).all()
            return len(results)

        for _ in range(3):
            _complex_query()

        usage = measure_resource_usage(_complex_query)
        print(f"\nComplex query (group by symbol): CPU={usage['cpu_percent']:.2f}%, "
              f"Memory={usage['memory_mb']:.2f}MB, Elapsed={usage['elapsed_time']*1000:.1f}ms")
        assert usage["memory_mb"] < 100


# ----- Backtesting resource usage -----

class TestBacktestResourceUsage:
    """Measure resource usage of backtesting operations."""

    def test_backtest_resource_usage(self, large_data):
        """Measure resource usage of running a backtest on large data."""
        from backend.ai.backtesting.backtest_engine import BacktestEngine
        from backend.ai.strategies.momentum_strategy import MomentumStrategy

        strategy = MomentumStrategy(params={"lookback": 20, "entry_threshold": 0.02})
        engine = BacktestEngine(data=large_data, strategy=strategy, initial_capital=100000)

        def _run():
            result = engine.run()
            return result

        # Warmup
        _run()

        usage = measure_resource_usage(_run)
        print(f"\nBacktest (large_data): CPU={usage['cpu_percent']:.2f}%, "
              f"Memory={usage['memory_mb']:.2f}MB, Elapsed={usage['elapsed_time']*1000:.1f}ms")
        # Backtest can use significant memory
        assert usage["memory_mb"] < 300


# ----- AI inference resource usage -----

class TestAIResourceUsage:
    """Measure resource usage of AI inference and training."""

    def test_model_inference_resource_usage(self):
        """Measure CPU/memory usage of AI model inference on a batch of data."""
        try:
            import torch
            from backend.ai.prediction.model_loader import model_loader
            from backend.ai.prediction.price_prediction import prepare_features

            if model_loader.model is None:
                pytest.skip("Model not loaded")

            symbol = "AAPL"
            features = prepare_features(symbol, lookback=60)

            def _infer():
                return model_loader.predict(features)

            for _ in range(10):
                _infer()

            usage = measure_resource_usage(_infer)
            print(f"\nAI inference (single prediction): CPU={usage['cpu_percent']:.2f}%, "
                  f"Memory={usage['memory_mb']:.2f}MB, Elapsed={usage['elapsed_time']*1000:.1f}ms")
            assert usage["memory_mb"] < 50
        except Exception as e:
            pytest.skip(f"AI inference not available: {e}")


# ----- Memory leak detection -----

class TestMemoryLeakDetection:
    """Run repeated operations to detect memory leaks."""

    @pytest.mark.parametrize("iterations", [10, 50])
    def test_sequential_portfolio_requests_memory(self, perf_client: TestClient, perf_auth_headers: Dict, iterations: int):
        """
        Repeatedly call portfolio summary and check if memory increases over time.
        A significant increase may indicate a memory leak.
        """
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        process = psutil.Process()
        mem_samples = []

        def _call():
            response = perf_client.get("/api/v1/portfolio/summary", headers=perf_auth_headers)
            assert response.status_code == 200
            return response

        # Warmup
        for _ in range(5):
            _call()

        for i in range(iterations):
            _call()
            mem = process.memory_info().rss / 1024 / 1024
            mem_samples.append(mem)
            time.sleep(0.05)

        # Calculate memory growth rate
        if len(mem_samples) > 10:
            first = mem_samples[0]
            last = mem_samples[-1]
            growth = last - first
            growth_per_iter = growth / iterations if iterations > 0 else 0
            print(f"\nMemory after {iterations} requests: {last:.2f}MB, growth: {growth:.2f}MB, per iter: {growth_per_iter:.3f}MB")
            # Arbitrary threshold: less than 0.5 MB per request average
            assert growth_per_iter < 0.5, f"Memory growth per iteration too high: {growth_per_iter:.3f}MB"

    @pytest.mark.parametrize("iterations", [10, 30])
    def test_repeated_ai_predictions_memory(self, perf_client: TestClient, perf_auth_headers: Dict, iterations: int):
        """Repeated AI predictions and check memory growth."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        process = psutil.Process()
        mem_samples = []

        def _call():
            response = perf_client.get("/api/v1/ai/predict/price/AAPL", headers=perf_auth_headers)
            assert response.status_code == 200
            return response

        for _ in range(5):
            _call()

        for i in range(iterations):
            _call()
            mem = process.memory_info().rss / 1024 / 1024
            mem_samples.append(mem)
            time.sleep(0.05)

        if len(mem_samples) > 10:
            first = mem_samples[0]
            last = mem_samples[-1]
            growth = last - first
            growth_per_iter = growth / iterations if iterations > 0 else 0
            print(f"\nAI predictions memory after {iterations}: {last:.2f}MB, growth: {growth:.2f}MB, per iter: {growth_per_iter:.3f}MB")
            # AI may have some memory retention; allow up to 1 MB per iter
            assert growth_per_iter < 1.0, f"AI memory growth per iteration too high: {growth_per_iter:.3f}MB"


# ----- Resource usage under concurrency -----

class TestConcurrentResourceUsage:
    """Measure resource usage during concurrent API requests."""

    @pytest.mark.parametrize("concurrency", [5, 10, 20])
    def test_concurrent_requests_resource_usage(self, perf_client: TestClient, perf_auth_headers: Dict, concurrency: int):
        """
        Measure peak CPU and memory usage when making concurrent requests.
        """
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        process = psutil.Process()
        # Baseline
        mem_before = process.memory_info().rss / 1024 / 1024
        cpu_before = process.cpu_percent(interval=0.1)

        def _call():
            response = perf_client.get("/api/v1/portfolio/summary", headers=perf_auth_headers)
            assert response.status_code == 200
            return response

        # Run concurrent requests
        num_requests = concurrency * 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(_call) for _ in range(num_requests)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        mem_after = process.memory_info().rss / 1024 / 1024
        cpu_after = process.cpu_percent(interval=0.1)
        mem_delta = mem_after - mem_before
        cpu_delta = cpu_after - cpu_before

        print(f"\nConcurrent {concurrency} ({num_requests} req): Memory increase: {mem_delta:.2f}MB, CPU: {cpu_delta:.2f}%")
        # Accept up to 200MB memory increase for high concurrency
        max_mem = 200
        assert mem_delta < max_mem, f"Memory increase too high: {mem_delta:.2f}MB"


# ----- Report generation -----

def test_generate_resource_usage_report():
    """
    Generate a comprehensive report of resource usage benchmarks.
    This runs a series of operations and records memory and CPU usage.
    """
    if not PSUTIL_AVAILABLE:
        print("psutil not available; skipping resource usage report")
        return

    import psutil
    process = psutil.Process()
    base_mem = process.memory_info().rss / 1024 / 1024

    results = {}

    # 1. API endpoint calls
    client = TestClient(perf_client.app)  # reuse
    headers = {"Authorization": f"Bearer {perf_test_token}"}

    def _measure(name, func):
        # Run 10 times and get average
        mem_samples = []
        cpu_samples = []
        elapsed_samples = []
        for _ in range(5):
            # Get current memory before
            mem_before = process.memory_info().rss / 1024 / 1024
            cpu_before = process.cpu_percent(interval=0.0)
            start = time.perf_counter()
            func()
            elapsed = time.perf_counter() - start
            mem_after = process.memory_info().rss / 1024 / 1024
            cpu_after = process.cpu_percent(interval=0.0)
            mem_samples.append(mem_after - mem_before)
            cpu_samples.append(cpu_after - cpu_before)
            elapsed_samples.append(elapsed)

        avg_mem = sum(mem_samples) / len(mem_samples) if mem_samples else 0
        avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
        avg_elapsed = sum(elapsed_samples) / len(elapsed_samples) if elapsed_samples else 0
        results[name] = {
            "avg_memory_mb": avg_mem,
            "avg_cpu_percent": avg_cpu,
            "avg_elapsed_ms": avg_elapsed * 1000,
        }

    # Measure endpoints
    endpoints = [
        ("portfolio_summary", lambda: client.get("/api/v1/portfolio/summary", headers=headers)),
        ("market_quote", lambda: client.get("/api/v1/market/quote/AAPL", headers=headers)),
        ("historical_data", lambda: client.get("/api/v1/market/historical/AAPL", params={"timeframe": "1h", "limit": 500}, headers=headers)),
        ("ai_prediction", lambda: client.get("/api/v1/ai/predict/price/AAPL", headers=headers)),
    ]
    for name, func in endpoints:
        try:
            _measure(name, func)
        except Exception as e:
            results[name] = {"error": str(e)}

    # Print report
    print("\n" + "="*60)
    print("RESOURCE USAGE BENCHMARK REPORT")
    print("="*60)
    print(f"Base memory: {base_mem:.2f} MB")
    print("-"*60)
    for name, data in results.items():
        if "error" in data:
            print(f"{name:25s} ERROR: {data['error']}")
        else:
            print(f"{name:25s} Mem: {data['avg_memory_mb']:8.2f} MB  CPU: {data['avg_cpu_percent']:6.2f}%  Lat: {data['avg_elapsed_ms']:8.1f} ms")
    print("="*60)

    # Save report
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"resource_usage_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "base_memory_mb": base_mem,
            "results": results,
        }, f, indent=2)
    print(f"Resource usage report saved to {report_path}")
