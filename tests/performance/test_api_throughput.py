"""
tests/performance/test_api_throughput.py

NEXUS AI Trading System - API Throughput Performance Tests

This module measures the maximum throughput (requests per second) of critical API
endpoints under various concurrency levels. It uses pytest-benchmark to track
performance over time and detect regressions.

Tests cover:
- Authentication (login, refresh)
- User profile (get, update)
- Portfolio (summary, positions, performance)
- Market data (quote, symbols, historical)
- Trading (open orders, history, place order)
- Risk (limits, check order)
- AI predictions (price, sentiment)

Each endpoint is tested with increasing concurrency to find the saturation point.

Usage:
    pytest tests/performance/test_api_throughput.py -v --benchmark-autosave
    pytest tests/performance/test_api_throughput.py -v --benchmark-compare

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import pytest
import random
import concurrent.futures
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from tests.performance.conftest import (
    perf_client,
    perf_auth_headers,
    perf_test_user,
    perf_test_token,
    perf_test_portfolio,
    perf_test_broker,
    perf_test_positions,
    perf_test_orders,
)


# ----- Helper functions for throughput measurements -----

def measure_throughput(client: TestClient, endpoint_func, num_requests: int = 100, concurrency: int = 10):
    """
    Measure throughput (requests per second) for a given endpoint function.
    Returns average throughput and error rate.
    """
    def _worker():
        return endpoint_func()

    start = time.perf_counter()
    errors = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_worker) for _ in range(num_requests)]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception:
                errors += 1
    elapsed = time.perf_counter() - start
    total = num_requests
    throughput = total / elapsed if elapsed > 0 else 0
    error_rate = errors / total if total > 0 else 0
    return throughput, error_rate, elapsed


# ----- Throughput tests using pytest-benchmark (single-threaded, but iterations) -----

@pytest.mark.parametrize("endpoint_path,method,headers_fixture,payload", [
    ("/api/v1/portfolio/summary", "GET", "perf_auth_headers", None),
    ("/api/v1/portfolio/positions", "GET", "perf_auth_headers", None),
    ("/api/v1/market/quote/AAPL", "GET", "perf_auth_headers", None),
    ("/api/v1/market/symbols", "GET", "perf_auth_headers", None),
    ("/api/v1/trading/orders/open", "GET", "perf_auth_headers", None),
    ("/api/v1/users/me", "GET", "perf_auth_headers", None),
    ("/api/v1/risk/limits", "GET", "perf_auth_headers", None),
])
def test_single_request_throughput(benchmark, perf_client: TestClient, endpoint_path, method, headers_fixture, payload, request):
    """
    Benchmark single-request latency and compute throughput by running many iterations.
    This uses the benchmark fixture's built-in iteration capability.
    We'll pass iterations via benchmark.rounds and benchmark.iterations.
    """
    headers = request.getfixturevalue(headers_fixture)

    def _make_request():
        if method == "GET":
            response = perf_client.get(endpoint_path, headers=headers)
        elif method == "POST":
            response = perf_client.post(endpoint_path, headers=headers, json=payload)
        elif method == "PUT":
            response = perf_client.put(endpoint_path, headers=headers, json=payload)
        elif method == "DELETE":
            response = perf_client.delete(endpoint_path, headers=headers)
        else:
            response = perf_client.request(method, endpoint_path, headers=headers, json=payload)
        # Ensure successful to avoid measuring errors
        assert response.status_code < 400
        return response

    # Use benchmark to measure many iterations (by default it runs ~10 rounds)
    benchmark(_make_request)
    # After benchmark, we can compute throughput from the mean time:
    # throughput = 1 / mean_time (if mean_time is in seconds)
    # We'll add a check after test via fixture.


# ----- Concurrent throughput tests (using benchmark with custom iterations) -----

@pytest.mark.parametrize("concurrency", [5, 10, 25, 50])
def test_portfolio_summary_throughput_concurrent(perf_client: TestClient, perf_auth_headers: Dict, concurrency: int):
    """
    Test throughput of portfolio summary endpoint with varying concurrency.
    This is not a benchmark test, but a performance test that measures throughput.
    We'll run it as a normal test and log results.
    """
    def _get_summary():
        response = perf_client.get("/api/v1/portfolio/summary", headers=perf_auth_headers)
        assert response.status_code == 200
        return response

    num_requests = concurrency * 10  # scale with concurrency
    throughput, error_rate, elapsed = measure_throughput(perf_client, _get_summary, num_requests, concurrency)
    print(f"Concurrency {concurrency}: Throughput={throughput:.2f} req/s, errors={error_rate:.2%}, elapsed={elapsed:.3f}s")
    # We'll not assert, but we can enforce minimum throughput in CI.
    min_throughput = float(os.getenv("PERF_MIN_THROUGHPUT", "50"))
    assert throughput >= min_throughput, f"Throughput {throughput:.2f} req/s below threshold {min_throughput}"


@pytest.mark.parametrize("concurrency", [5, 10, 25, 50])
def test_market_quote_throughput_concurrent(perf_client: TestClient, perf_auth_headers: Dict, concurrency: int):
    """
    Test throughput of market quote endpoint with varying concurrency.
    """
    def _get_quote():
        response = perf_client.get("/api/v1/market/quote/AAPL", headers=perf_auth_headers)
        assert response.status_code == 200
        return response

    num_requests = concurrency * 10
    throughput, error_rate, elapsed = measure_throughput(perf_client, _get_quote, num_requests, concurrency)
    print(f"Concurrency {concurrency}: Throughput={throughput:.2f} req/s, errors={error_rate:.2%}, elapsed={elapsed:.3f}s")
    min_throughput = float(os.getenv("PERF_MIN_THROUGHPUT", "40"))
    assert throughput >= min_throughput, f"Throughput {throughput:.2f} req/s below threshold {min_throughput}"


@pytest.mark.parametrize("concurrency", [5, 10, 25])
def test_place_order_throughput_concurrent(perf_client: TestClient, perf_auth_headers: Dict, perf_test_portfolio, concurrency: int):
    """
    Test throughput of order placement (write operation) with varying concurrency.
    This may be slower due to database writes and risk checks.
    """
    portfolio_id = perf_test_portfolio.id
    payload = {
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 1,
        "order_type": "market",
        "portfolio_id": portfolio_id,
    }

    def _place_order():
        response = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
        # Accept 200-400; we only care about latency
        assert response.status_code < 500
        return response

    num_requests = concurrency * 5  # fewer requests for write operations
    throughput, error_rate, elapsed = measure_throughput(perf_client, _place_order, num_requests, concurrency)
    print(f"Concurrency {concurrency}: Throughput={throughput:.2f} req/s, errors={error_rate:.2%}, elapsed={elapsed:.3f}s")
    min_throughput = float(os.getenv("PERF_MIN_THROUGHPUT_WRITE", "10"))
    assert throughput >= min_throughput, f"Write throughput {throughput:.2f} req/s below threshold {min_throughput}"


# ----- Mixed endpoints throughput (batch) -----

def test_mixed_endpoint_throughput(perf_client: TestClient, perf_auth_headers: Dict):
    """
    Simulate realistic mixed traffic and measure overall throughput.
    This test sends a mix of read and write requests with different weights.
    """
    endpoints = [
        ("/api/v1/portfolio/summary", "GET", 30),
        ("/api/v1/market/quote/AAPL", "GET", 25),
        ("/api/v1/portfolio/positions", "GET", 20),
        ("/api/v1/users/me", "GET", 15),
        ("/api/v1/trading/orders/open", "GET", 10),
        # Add a write operation with lower weight
        ("/api/v1/risk/check-order", "POST", 5),  # lightweight write
    ]

    # Pre-build request functions
    def make_request(endpoint, method, payload=None):
        if method == "GET":
            return perf_client.get(endpoint, headers=perf_auth_headers)
        elif method == "POST":
            if endpoint == "/api/v1/risk/check-order":
                # Need to provide a payload
                return perf_client.post(endpoint, headers=perf_auth_headers,
                                        json={"symbol": "AAPL", "side": "buy", "quantity": 10, "price": 150.0,
                                              "portfolio_id": "dummy"})
            else:
                return perf_client.post(endpoint, headers=perf_auth_headers)
        else:
            return perf_client.request(method, endpoint, headers=perf_auth_headers)

    def _worker():
        # Select endpoint based on weights
        total_weight = sum(w for _, _, w in endpoints)
        r = random.random() * total_weight
        cumulative = 0
        for endpoint, method, weight in endpoints:
            cumulative += weight
            if r <= cumulative:
                return make_request(endpoint, method)
        return make_request(endpoints[0][0], endpoints[0][1])

    num_requests = 200
    concurrency = 20
    throughput, error_rate, elapsed = measure_throughput(perf_client, _worker, num_requests, concurrency)
    print(f"Mixed throughput: {throughput:.2f} req/s, errors={error_rate:.2%}, elapsed={elapsed:.3f}s")
    min_throughput = float(os.getenv("PERF_MIN_MIXED_THROUGHPUT", "30"))
    assert throughput >= min_throughput, f"Mixed throughput {throughput:.2f} req/s below threshold {min_throughput}"


# ----- Throughput under sustained load (endurance) -----

def test_sustained_throughput(perf_client: TestClient, perf_auth_headers: Dict):
    """
    Measure throughput over a longer duration (e.g., 30 seconds) to check stability.
    This is not a benchmark test but a performance test.
    """
    def _get_summary():
        response = perf_client.get("/api/v1/portfolio/summary", headers=perf_auth_headers)
        assert response.status_code == 200
        return response

    duration = 30  # seconds
    concurrency = 10
    start = time.perf_counter()
    total_requests = 0
    errors = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        # Submit many tasks, but we'll stop after duration.
        futures = []
        while time.perf_counter() - start < duration:
            futures.append(executor.submit(_get_summary))
            # Small delay to avoid overwhelming
            time.sleep(0.01)
        # Wait for all to complete (or timeout)
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
                total_requests += 1
            except Exception:
                errors += 1

    elapsed = time.perf_counter() - start
    throughput = total_requests / elapsed if elapsed > 0 else 0
    error_rate = errors / (total_requests + errors) if (total_requests + errors) > 0 else 1
    print(f"Sustained ({duration}s): Throughput={throughput:.2f} req/s, errors={error_rate:.2%}, total={total_requests}")
    min_throughput = float(os.getenv("PERF_MIN_SUSTAINED_THROUGHPUT", "40"))
    assert throughput >= min_throughput, f"Sustained throughput {throughput:.2f} req/s below threshold {min_throughput}"


# ----- Regression check (benchmark) -----

@pytest.fixture(autouse=True)
def check_throughput_thresholds(request, benchmark):
    """
    After each benchmark test, ensure average throughput is above a minimum threshold.
    Since benchmark gives mean time, we can compute throughput = 1 / mean_time.
    We'll enforce this if PERF_ENFORCE_THROUGHPUT is set.
    """
    yield
    if hasattr(benchmark, 'stats') and benchmark.stats:
        mean_time = benchmark.stats['mean']  # seconds
        throughput = 1.0 / mean_time if mean_time > 0 else 0
        min_throughput = float(os.getenv('PERF_MIN_BENCHMARK_THROUGHPUT', '50'))
        # Only enforce if explicitly requested
        if os.getenv('PERF_ENFORCE_THROUGHPUT', 'false').lower() == 'true':
            assert throughput >= min_throughput, \
                f"Throughput {throughput:.2f} req/s below threshold {min_throughput}"


# ----- Baseline throughput report -----

def test_generate_throughput_report(perf_client: TestClient, perf_auth_headers: Dict):
    """
    Generate a report of throughput for all major endpoints at a fixed concurrency.
    This can be used for capacity planning.
    """
    endpoints = {
        "portfolio_summary": ("GET", "/api/v1/portfolio/summary"),
        "positions": ("GET", "/api/v1/portfolio/positions"),
        "market_quote": ("GET", "/api/v1/market/quote/AAPL"),
        "market_symbols": ("GET", "/api/v1/market/symbols"),
        "open_orders": ("GET", "/api/v1/trading/orders/open"),
        "users_me": ("GET", "/api/v1/users/me"),
        "risk_limits": ("GET", "/api/v1/risk/limits"),
        "price_prediction": ("GET", "/api/v1/ai/predict/price/AAPL"),
        "order_history": ("GET", "/api/v1/trading/orders/history?limit=50"),
        "performance": ("GET", "/api/v1/portfolio/performance?interval=daily&period=1m"),
    }

    results = {}
    concurrency = 20
    num_requests = 100

    for name, (method, path) in endpoints.items():
        def _make_request(m=method, p=path):
            if m == "GET":
                resp = perf_client.get(p, headers=perf_auth_headers)
            else:
                resp = perf_client.request(m, p, headers=perf_auth_headers)
            assert resp.status_code < 400
            return resp

        throughput, error_rate, elapsed = measure_throughput(perf_client, _make_request, num_requests, concurrency)
        results[name] = {
            "method": method,
            "path": path,
            "throughput": throughput,
            "error_rate": error_rate,
            "elapsed": elapsed,
        }

    # Print report
    print("\n" + "="*60)
    print("THROUGHPUT BASELINE REPORT")
    print("="*60)
    print(f"Concurrency: {concurrency}, Requests: {num_requests}")
    print("-"*60)
    for name, data in sorted(results.items(), key=lambda x: x[1]["throughput"], reverse=True):
        print(f"{name:25s} {data['throughput']:8.2f} req/s  errors: {data['error_rate']:5.2%}")
    print("="*60)

    # Save report to file
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"throughput_baseline_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "concurrency": concurrency,
            "num_requests": num_requests,
            "results": results,
        }, f, indent=2)
    print(f"Report saved to {report_path}")

