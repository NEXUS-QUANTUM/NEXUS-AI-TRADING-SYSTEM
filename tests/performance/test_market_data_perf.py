
"""
tests/performance/test_market_data_perf.py

NEXUS AI Trading System - Market Data Performance Tests

This module uses pytest-benchmark to measure the performance of market data
endpoints, which are critical for real-time trading and analytics. It tests:

- Quote retrieval (single symbol)
- Bulk quote retrieval (multiple symbols)
- Historical data (various timeframes and limits)
- Order book data
- Symbols list (with filters)
- Intraday data (1min, 5min, 15min)
- Real-time streaming (simulated via WebSocket)
- Cache efficiency

These benchmarks help ensure market data endpoints meet latency requirements
for high-frequency trading and real-time monitoring.

Usage:
    pytest tests/performance/test_market_data_perf.py -v --benchmark-autosave
    pytest tests/performance/test_market_data_perf.py -v --benchmark-compare

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

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from fastapi.testclient import TestClient

from tests.performance.conftest import (
    perf_client,
    perf_auth_headers,
    perf_test_user,
    perf_test_token,
)


# ----- Helper functions -----

def create_session_with_pool(pool_size: int = 50) -> requests.Session:
    """Create a requests session with connection pooling for performance tests."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE"],
    )
    adapter = HTTPAdapter(
        pool_connections=pool_size,
        pool_maxsize=pool_size,
        max_retries=retries,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def make_request(session: requests.Session, url: str, method: str = "GET", headers: Dict = None, params: Dict = None):
    """Make a request and return (latency, success)."""
    start = time.perf_counter()
    try:
        if method.upper() == "GET":
            response = session.get(url, headers=headers, params=params, timeout=10)
        elif method.upper() == "POST":
            response = session.post(url, headers=headers, json=params, timeout=10)
        else:
            response = session.request(method, url, headers=headers, json=params, timeout=10)
        latency = time.perf_counter() - start
        success = response.status_code < 400
        return latency, success
    except Exception:
        return time.perf_counter() - start, False


def generate_test_symbols(count: int = 10) -> List[str]:
    """Generate a list of test symbols."""
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "SPY", "QQQ"]
    if count <= len(symbols):
        return symbols[:count]
    # Extend with dummy symbols if needed
    extra = [f"SYM{i}" for i in range(len(symbols), count)]
    return symbols + extra


# ----- Fixtures -----

@pytest.fixture(scope="function")
def session_pool() -> requests.Session:
    """Create a session with a connection pool for concurrent tests."""
    return create_session_with_pool(100)


@pytest.fixture(scope="function")
def base_url() -> str:
    """Base URL for the API."""
    return os.getenv("NEXUS_LOAD_TEST_BASE_URL", "http://localhost:8000/api/v1")


@pytest.fixture(scope="function")
def symbols_10() -> List[str]:
    """10 test symbols."""
    return generate_test_symbols(10)


@pytest.fixture(scope="function")
def symbols_20() -> List[str]:
    """20 test symbols."""
    return generate_test_symbols(20)


# ----- Quote performance benchmarks -----

class TestQuoteLatency:
    """Benchmark quote retrieval latency."""

    @pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"])
    def test_quote_latency_single(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, symbol: str):
        """Benchmark retrieving a single quote."""
        @benchmark
        def _get_quote():
            response = perf_client.get(f"/api/v1/market/quote/{symbol}", headers=perf_auth_headers)
            assert response.status_code == 200
            return response

    def test_quote_latency_bulk_10(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, symbols_10: List[str]):
        """Benchmark retrieving 10 quotes in bulk."""
        params = {"symbols": ",".join(symbols_10)}

        @benchmark
        def _bulk_quotes():
            response = perf_client.get("/api/v1/market/quote/bulk", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response

    def test_quote_latency_bulk_20(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, symbols_20: List[str]):
        """Benchmark retrieving 20 quotes in bulk."""
        params = {"symbols": ",".join(symbols_20)}

        @benchmark
        def _bulk_quotes():
            response = perf_client.get("/api/v1/market/quote/bulk", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response


# ----- Historical data performance -----

class TestHistoricalDataLatency:
    """Benchmark historical data retrieval."""

    @pytest.mark.parametrize("timeframe,limit", [
        ("1m", 100),
        ("5m", 1000),
        ("15m", 500),
        ("1h", 1000),
        ("1d", 500),
        ("1h", 5000),
        ("1d", 1000),
    ])
    def test_historical_data(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, timeframe: str, limit: int):
        """Benchmark historical data with various timeframes and limits."""
        symbol = "AAPL"
        params = {"timeframe": timeframe, "limit": limit}

        @benchmark
        def _get_historical():
            response = perf_client.get(f"/api/v1/market/historical/{symbol}", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response

    @pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "BTC/USD", "EUR/USD"])
    def test_historical_data_by_symbol(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, symbol: str):
        """Benchmark historical data for different symbol types."""
        params = {"timeframe": "1h", "limit": 500}

        @benchmark
        def _get_historical():
            response = perf_client.get(f"/api/v1/market/historical/{symbol}", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response


# ----- Order book performance -----

class TestOrderBookLatency:
    """Benchmark order book retrieval."""

    def test_order_book_depth_small(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """Benchmark retrieving order book with small depth."""
        params = {"depth": 10}
        @benchmark
        def _get_orderbook():
            response = perf_client.get("/api/v1/market/orderbook/AAPL", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response

    def test_order_book_depth_large(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """Benchmark retrieving order book with large depth."""
        params = {"depth": 100}
        @benchmark
        def _get_orderbook():
            response = perf_client.get("/api/v1/market/orderbook/AAPL", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response


# ----- Symbols list performance -----

class TestSymbolsListLatency:
    """Benchmark symbols list retrieval."""

    def test_symbols_list(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """Benchmark retrieving the full symbols list."""
        @benchmark
        def _get_symbols():
            response = perf_client.get("/api/v1/market/symbols", headers=perf_auth_headers)
            assert response.status_code == 200
            return response

    def test_symbols_with_filter(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """Benchmark retrieving symbols with a filter."""
        params = {"type": "stock", "sector": "technology"}
        @benchmark
        def _get_symbols_filtered():
            response = perf_client.get("/api/v1/market/symbols", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response


# ----- Concurrent market data requests -----

class TestMarketDataConcurrency:
    """Benchmark concurrent market data requests."""

    @pytest.mark.parametrize("concurrency", [5, 10, 25])
    def test_concurrent_quotes(self, benchmark, session_pool, base_url, perf_auth_headers, concurrency):
        """Benchmark concurrent quote requests."""
        url = f"{base_url}/market/quote/AAPL"
        headers = perf_auth_headers

        def _request():
            return make_request(session_pool, url, "GET", headers=headers)

        @benchmark
        def _concurrent():
            num_requests = concurrency * 5
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(_request) for _ in range(num_requests)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                successes = sum(1 for _, ok in results if ok)
                return successes / num_requests

    @pytest.mark.parametrize("concurrency", [5, 10, 25])
    def test_concurrent_historical(self, benchmark, session_pool, base_url, perf_auth_headers, concurrency):
        """Benchmark concurrent historical data requests."""
        url = f"{base_url}/market/historical/AAPL"
        params = {"timeframe": "1h", "limit": 100}
        headers = perf_auth_headers

        def _request():
            return make_request(session_pool, url, "GET", headers=headers, params=params)

        @benchmark
        def _concurrent():
            num_requests = concurrency * 3  # historical is heavier
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(_request) for _ in range(num_requests)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                successes = sum(1 for _, ok in results if ok)
                return successes / num_requests

    @pytest.mark.parametrize("concurrency", [5, 10, 25])
    def test_concurrent_bulk_quotes(self, benchmark, session_pool, base_url, perf_auth_headers, concurrency, symbols_10):
        """Benchmark concurrent bulk quote requests."""
        url = f"{base_url}/market/quote/bulk"
        params = {"symbols": ",".join(symbols_10)}
        headers = perf_auth_headers

        def _request():
            return make_request(session_pool, url, "GET", headers=headers, params=params)

        @benchmark
        def _concurrent():
            num_requests = concurrency * 4
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(_request) for _ in range(num_requests)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                successes = sum(1 for _, ok in results if ok)
                return successes / num_requests


# ----- Cache performance for market data -----

class TestMarketDataCache:
    """Benchmark cache efficiency for market data endpoints."""

    def test_cached_quote_vs_uncached(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """
        Compare performance of cached vs uncached quote requests.
        We'll use two consecutive calls: the first should be uncached (or cache miss),
        the second should be cached (cache hit).
        """
        symbol = "AAPL"
        headers = perf_auth_headers

        # First call (likely uncached)
        @benchmark
        def _uncached():
            response = perf_client.get(f"/api/v1/market/quote/{symbol}", headers=headers)
            assert response.status_code == 200
            return response

        # Second call (should be cached)
        @benchmark
        def _cached():
            response = perf_client.get(f"/api/v1/market/quote/{symbol}", headers=headers)
            assert response.status_code == 200
            return response

        # Note: benchmark will time both; we can compare results after.

    def test_cached_historical_data(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """Benchmark cached historical data retrieval."""
        params = {"timeframe": "1h", "limit": 500}
        symbol = "AAPL"
        headers = perf_auth_headers

        # Warm up cache
        perf_client.get(f"/api/v1/market/historical/{symbol}", params=params, headers=headers)

        # Measure cached response
        @benchmark
        def _cached():
            response = perf_client.get(f"/api/v1/market/historical/{symbol}", params=params, headers=headers)
            assert response.status_code == 200
            return response


# ----- Real-time streaming (WebSocket) performance -----

class TestWebSocketMarketData:
    """Benchmark WebSocket performance for real-time market data."""

    @pytest.mark.skip(reason="WebSocket performance tests require additional setup")
    def test_websocket_connection_latency(self):
        """Benchmark WebSocket connection establishment latency."""
        pass

    @pytest.mark.skip(reason="WebSocket performance tests require additional setup")
    def test_websocket_message_throughput(self):
        """Benchmark WebSocket message throughput."""
        pass


# ----- Bulk data export performance -----

class TestBulkDataExport:
    """Benchmark bulk data export endpoints."""

    def test_export_historical_data(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """Benchmark exporting large historical datasets."""
        params = {
            "symbols": "AAPL,MSFT,GOOGL",
            "timeframe": "1h",
            "start_date": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "format": "json",
        }
        @benchmark
        def _export():
            response = perf_client.get("/api/v1/market/export", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response

    def test_export_order_book(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """Benchmark exporting order book snapshots."""
        params = {"symbols": "AAPL,MSFT", "depth": 20}
        @benchmark
        def _export():
            response = perf_client.get("/api/v1/market/orderbook/export", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response


# ----- Parameterized performance (various symbols) -----

@pytest.mark.parametrize("symbol", ["AAPL", "BTC/USD", "EUR/USD", "SPY", "TSLA"])
def test_quote_by_symbol_type(benchmark, perf_client: TestClient, perf_auth_headers: Dict, symbol: str):
    """Benchmark quote retrieval for different asset types."""
    @benchmark
    def _get_quote():
        response = perf_client.get(f"/api/v1/market/quote/{symbol}", headers=perf_auth_headers)
        assert response.status_code == 200
        return response


# ----- Report generation -----

def test_generate_market_data_performance_report():
    """
    Generate a comprehensive report of market data performance metrics.
    This runs a series of tests and records results for comparison.
    """
    import time
    import json
    from datetime import datetime

    base_url = os.getenv("NEXUS_LOAD_TEST_BASE_URL", "http://localhost:8000/api/v1")
    auth_token = os.getenv("TEST_USER_TOKEN")
    if not auth_token:
        # Try to get a token via login
        import requests
        login_resp = requests.post(
            f"{base_url}/auth/login",
            json={"email": "test@nexusquantum.com", "password": "Test@123"}
        )
        if login_resp.status_code == 200:
            auth_token = login_resp.json().get("access_token")
        else:
            print("Could not get auth token; skipping report generation")
            return

    headers = {"Authorization": f"Bearer {auth_token}"}
    session = create_session_with_pool(20)

    endpoints = [
        ("quote_single", "/market/quote/AAPL", {}),
        ("quote_bulk_10", "/market/quote/bulk", {"symbols": "AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,META,NFLX,SPY,QQQ"}),
        ("historical_1h_100", "/market/historical/AAPL", {"timeframe": "1h", "limit": 100}),
        ("historical_1h_500", "/market/historical/AAPL", {"timeframe": "1h", "limit": 500}),
        ("historical_1d_1000", "/market/historical/AAPL", {"timeframe": "1d", "limit": 1000}),
        ("orderbook_depth_10", "/market/orderbook/AAPL", {"depth": 10}),
        ("orderbook_depth_50", "/market/orderbook/AAPL", {"depth": 50}),
        ("symbols", "/market/symbols", {}),
    ]

    results = {}
    for name, path, params in endpoints:
        url = f"{base_url}{path}"
        latencies = []
        successes = 0
        for _ in range(10):  # run 10 iterations
            lat, ok = make_request(session, url, "GET", headers=headers, params=params)
            latencies.append(lat)
            if ok:
                successes += 1
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        p95 = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
        error_rate = 1 - (successes / len(latencies)) if latencies else 1.0
        results[name] = {
            "avg_latency_ms": avg_lat * 1000,
            "p95_latency_ms": p95 * 1000,
            "error_rate": error_rate,
        }
        print(f"{name}: avg={avg_lat*1000:.1f}ms, p95={p95*1000:.1f}ms, errors={error_rate:.2%}")

    # Save report
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"market_data_perf_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }, f, indent=2)
    print(f"Market data performance report saved to {report_path}")
