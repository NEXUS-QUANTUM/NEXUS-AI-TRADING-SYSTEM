"""
tests/performance/test_api_latency.py

NEXUS AI Trading System - API Latency Performance Tests

This module uses pytest-benchmark to measure and track the latency of
critical API endpoints. It establishes baseline latency metrics and
detects performance regressions.

Tests cover:
- Authentication (login, refresh, logout)
- User profile (get, update)
- Portfolio (summary, positions, performance)
- Market data (quote, symbols, historical)
- Trading (place order, cancel, open orders)
- Risk management (limits, check order)
- AI predictions (price, sentiment)

Each endpoint is benchmarked with realistic request payloads and
authenticated context where required.

Usage:
    pytest tests/performance/test_api_latency.py -v --benchmark-autosave
    pytest tests/performance/test_api_latency.py -v --benchmark-compare

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import pytest
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

# Import fixtures from conftest
from tests.performance.conftest import (
    perf_client,
    perf_auth_headers,
    perf_test_user,
    perf_test_token,
    perf_test_portfolio,
    perf_test_broker,
    perf_test_positions,
    perf_test_orders,
    perf_benchmark_rounds,
    perf_benchmark_iterations,
)


# ----- Helper Functions -----

def benchmark_endpoint(benchmark, client: TestClient, method: str, path: str,
                       headers: Dict = None, data: Dict = None, params: Dict = None):
    """
    Benchmark a single API endpoint call.
    The benchmark fixture will run the function multiple times.
    """
    def _make_request():
        if method.upper() == "GET":
            return client.get(path, headers=headers, params=params)
        elif method.upper() == "POST":
            return client.post(path, headers=headers, json=data, params=params)
        elif method.upper() == "PUT":
            return client.put(path, headers=headers, json=data, params=params)
        elif method.upper() == "DELETE":
            return client.delete(path, headers=headers, params=params)
        else:
            return client.request(method, path, headers=headers, json=data, params=params)

    # The benchmark fixture will call the function and measure time
    # We need to capture the response for potential assertions outside benchmark.
    # We'll wrap it in a function that also returns the response for inspection.
    # But benchmark doesn't support returning values easily. We'll just execute.
    # Instead, we'll use benchmark.pedantic or manual loop.
    # For simplicity, we'll use a manual loop and measure using time.perf_counter.
    # But we want to leverage pytest-benchmark's features, so we'll use the benchmark fixture.
    # We'll define a function that returns the response time.
    def _wrapped():
        start = time.perf_counter()
        response = _make_request()
        end = time.perf_counter()
        # Ensure response is successful to avoid measuring errors.
        # We'll not assert here to keep benchmark pure.
        return end - start

    # Use benchmark to measure _wrapped
    # But we need to ensure the request is actually made.
    # Better approach: use benchmark with a lambda that makes the request.
    # However, we'll use benchmark.pedantic to run iterations.
    # For simplicity, we'll just call the endpoint and let benchmark measure the whole call.
    # The benchmark fixture will call the function and time it.
    # We'll use a lambda that returns the response so we can check status.
    # But benchmark doesn't care about return value.
    # We'll use the `benchmark` fixture as a decorator:
    # @benchmark
    # def test_something(client):
    #    client.get(...)
    # That's how pytest-benchmark works. We'll write individual test functions
    # that use the benchmark fixture directly.

    # So we won't use this helper function directly; we'll implement tests with benchmark fixture.
    pass


# ----- Authentication Endpoints -----

def test_login_latency(benchmark, perf_client: TestClient, perf_test_user):
    """Benchmark login endpoint latency."""
    payload = {
        "email": perf_test_user.email,
        "password": "PerfTest@123",  # Password from fixture
    }

    @benchmark
    def _login():
        response = perf_client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 200
        return response

    # The benchmark will run this multiple times and report stats.


def test_refresh_latency(benchmark, perf_client: TestClient, perf_test_token):
    """Benchmark token refresh endpoint latency."""
    payload = {"refresh_token": perf_test_token}  # Need a real refresh token

    # We need to get a refresh token first. We can reuse login to get refresh token.
    # For simplicity, we'll use a static refresh token from the test user fixture.
    # We can create a fixture that returns a refresh token.
    # We'll assume we have a fixture 'perf_test_refresh_token' defined in conftest.
    # Since we don't, we'll generate one using the create_refresh_token function.
    from backend.security.auth import create_refresh_token
    refresh_token = create_refresh_token(data={"sub": perf_test_user.id})

    @benchmark
    def _refresh():
        response = perf_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        return response


def test_logout_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark logout endpoint latency."""
    @benchmark
    def _logout():
        response = perf_client.post("/api/v1/auth/logout", headers=perf_auth_headers)
        assert response.status_code in [200, 204]
        return response


# ----- User Profile Endpoints -----

def test_get_user_profile_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark GET /api/v1/users/me latency."""
    @benchmark
    def _get_profile():
        response = perf_client.get("/api/v1/users/me", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


def test_update_user_profile_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark PUT /api/v1/users/me latency."""
    payload = {
        "first_name": "PerfUpdated",
        "last_name": "Benchmark",
        # Keep email unchanged
    }
    @benchmark
    def _update_profile():
        response = perf_client.put("/api/v1/users/me", json=payload, headers=perf_auth_headers)
        assert response.status_code == 200
        return response


# ----- Portfolio Endpoints -----

def test_portfolio_summary_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark portfolio summary endpoint latency."""
    @benchmark
    def _portfolio_summary():
        response = perf_client.get("/api/v1/portfolio/summary", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


def test_positions_list_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark list positions endpoint latency."""
    @benchmark
    def _positions():
        response = perf_client.get("/api/v1/portfolio/positions", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


def test_performance_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark portfolio performance endpoint latency."""
    params = {"interval": "daily", "period": "1m"}
    @benchmark
    def _performance():
        response = perf_client.get("/api/v1/portfolio/performance", params=params, headers=perf_auth_headers)
        assert response.status_code == 200
        return response


# ----- Market Data Endpoints -----

def test_market_quote_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark market quote endpoint latency."""
    symbol = "AAPL"
    @benchmark
    def _quote():
        response = perf_client.get(f"/api/v1/market/quote/{symbol}", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


def test_market_symbols_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark market symbols endpoint latency."""
    @benchmark
    def _symbols():
        response = perf_client.get("/api/v1/market/symbols", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


def test_historical_data_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark historical data endpoint latency."""
    params = {"timeframe": "1h", "limit": 100}
    @benchmark
    def _historical():
        response = perf_client.get("/api/v1/market/historical/AAPL", params=params, headers=perf_auth_headers)
        assert response.status_code == 200
        return response


# ----- Trading Endpoints -----

def test_open_orders_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark open orders endpoint latency."""
    @benchmark
    def _open_orders():
        response = perf_client.get("/api/v1/trading/orders/open", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


def test_order_history_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark order history endpoint latency."""
    params = {"limit": 50}
    @benchmark
    def _history():
        response = perf_client.get("/api/v1/trading/orders/history", params=params, headers=perf_auth_headers)
        assert response.status_code == 200
        return response


def test_place_order_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict, perf_test_portfolio):
    """Benchmark order placement endpoint latency."""
    portfolio_id = perf_test_portfolio.id
    payload = {
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 1,
        "order_type": "market",
        "portfolio_id": portfolio_id,
    }
    @benchmark
    def _place_order():
        response = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
        # The order may be rejected if balance is insufficient, but we just measure latency.
        # We'll assert a 200-400 status (accept any response)
        assert response.status_code < 500
        return response


# ----- Risk Management Endpoints -----

def test_risk_limits_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark risk limits endpoint latency."""
    @benchmark
    def _risk_limits():
        response = perf_client.get("/api/v1/risk/limits", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


def test_check_order_risk_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict, perf_test_portfolio):
    """Benchmark check-order risk endpoint latency."""
    portfolio_id = perf_test_portfolio.id
    payload = {
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 10,
        "price": 150.0,
        "portfolio_id": portfolio_id,
    }
    @benchmark
    def _check_risk():
        response = perf_client.post("/api/v1/risk/check-order", json=payload, headers=perf_auth_headers)
        assert response.status_code == 200
        return response


# ----- AI Prediction Endpoints -----

def test_price_prediction_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark price prediction endpoint latency."""
    symbol = "AAPL"
    @benchmark
    def _prediction():
        response = perf_client.get(f"/api/v1/ai/predict/price/{symbol}", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


def test_sentiment_analysis_latency(benchmark, perf_client: TestClient, perf_auth_headers: Dict):
    """Benchmark sentiment analysis endpoint latency."""
    symbol = "AAPL"
    @benchmark
    def _sentiment():
        response = perf_client.get(f"/api/v1/ai/predict/sentiment/{symbol}", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


# ----- Parameterized Benchmarks (grouped endpoints) -----

@pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "GOOGL"])
def test_market_quote_various_symbols(benchmark, perf_client: TestClient, perf_auth_headers: Dict, symbol: str):
    """Benchmark market quote for different symbols."""
    @benchmark
    def _quote():
        response = perf_client.get(f"/api/v1/market/quote/{symbol}", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


@pytest.mark.parametrize("timeframe,limit", [("1h", 100), ("1d", 500), ("1w", 50)])
def test_historical_various_params(benchmark, perf_client: TestClient, perf_auth_headers: Dict, timeframe: str, limit: int):
    """Benchmark historical data with various parameters."""
    params = {"timeframe": timeframe, "limit": limit}
    @benchmark
    def _historical():
        response = perf_client.get("/api/v1/market/historical/AAPL", params=params, headers=perf_auth_headers)
        assert response.status_code == 200
        return response


# ----- Bulk / Concurrent Simulation (not using benchmark, but direct timing) -----

def test_bulk_concurrent_requests(perf_client: TestClient, perf_auth_headers: Dict):
    """
    Test latency under concurrency by sending multiple requests in parallel.
    This measures total time for a batch of requests, not per-request latency.
    We'll use time.perf_counter and concurrent.futures.
    This is not a benchmark test per se, but a performance test.
    """
    import concurrent.futures
    import time

    def _make_request():
        response = perf_client.get("/api/v1/portfolio/summary", headers=perf_auth_headers)
        assert response.status_code == 200
        return response

    num_requests = 20
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_make_request) for _ in range(num_requests)]
        for f in concurrent.futures.as_completed(futures):
            f.result()  # Raise any exception
    elapsed = time.perf_counter() - start
    avg = elapsed / num_requests
    print(f"Concurrent {num_requests} requests total: {elapsed:.3f}s, avg: {avg*1000:.1f}ms")
    # We'll not assert, just log; can be used for manual observation.
    # We could add a threshold assertion based on expected performance.


# ----- Baseline Assertions (optional) -----

# These can be used to enforce performance regressions in CI.
# We'll add a fixture to check benchmark results after each test.
# We'll use pytest-benchmark's built-in `benchmark` fixture's stats.

@pytest.fixture(autouse=True)
def check_latency_thresholds(request, benchmark):
    """
    After each benchmark test, check that the average latency is below a threshold.
    The threshold is set via environment variable PERF_MAX_LATENCY_MS (default 500ms).
    This fixture runs after each test.
    """
    yield
    # After the test, check if benchmark.stats is available.
    if hasattr(benchmark, 'stats'):
        # For tests that don't use benchmark fixture, this will be None.
        # We'll only check tests that use the benchmark fixture.
        if hasattr(benchmark, 'stats') and benchmark.stats:
            avg = benchmark.stats['mean']  # in seconds
            max_latency_ms = int(os.getenv('PERF_MAX_LATENCY_MS', '500'))
            # Convert avg to ms
            avg_ms = avg * 1000
            if avg_ms > max_latency_ms:
                # We can log a warning or fail the test.
                # For CI, fail the test to prevent regression.
                assert avg_ms <= max_latency_ms, \
                    f"Latency {avg_ms:.1f}ms exceeds threshold {max_latency_ms}ms"

    # Also, we could write results to a file for historical tracking.
    # Not implemented here.
