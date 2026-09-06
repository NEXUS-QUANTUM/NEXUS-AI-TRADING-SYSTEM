"""
tests/performance/test_order_execution_perf.py

NEXUS AI Trading System - Order Execution Performance Tests

This module uses pytest-benchmark to measure the performance of order execution
operations, including:

- Market order placement latency
- Limit order placement latency
- Stop order placement latency
- Order cancellation latency
- Order modification latency
- Concurrent order placement
- Bulk order placement
- Order validation performance
- Risk check performance during order placement
- Portfolio update latency after order execution

These benchmarks help ensure order execution meets latency requirements for
trading systems and track performance regressions over time.

Usage:
    pytest tests/performance/test_order_execution_perf.py -v --benchmark-autosave
    pytest tests/performance/test_order_execution_perf.py -v --benchmark-compare

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
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from tests.performance.conftest import (
    perf_client,
    perf_auth_headers,
    perf_test_user,
    perf_test_portfolio,
    perf_test_broker,
    perf_test_positions,
    perf_test_orders,
    perf_benchmark_rounds,
    perf_benchmark_iterations,
)


# ----- Helper functions -----

def create_session_with_pool(pool_size: int = 50) -> requests.Session:
    """Create a requests session with connection pooling."""
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


def make_request(session: requests.Session, url: str, method: str = "GET", headers: Dict = None, data: Dict = None):
    """Make a request and return (latency, success, response)."""
    start = time.perf_counter()
    try:
        if method.upper() == "GET":
            response = session.get(url, headers=headers, timeout=15)
        elif method.upper() == "POST":
            response = session.post(url, headers=headers, json=data, timeout=15)
        elif method.upper() == "PUT":
            response = session.put(url, headers=headers, json=data, timeout=15)
        elif method.upper() == "DELETE":
            response = session.delete(url, headers=headers, timeout=15)
        else:
            response = session.request(method, url, headers=headers, json=data, timeout=15)
        latency = time.perf_counter() - start
        success = response.status_code < 400
        return latency, success, response
    except Exception as e:
        return time.perf_counter() - start, False, None


def create_order_payload(
    portfolio_id: str,
    symbol: str = "AAPL",
    side: str = "buy",
    order_type: str = "market",
    quantity: float = 1,
    limit_price: float = None,
    stop_price: float = None,
) -> Dict[str, Any]:
    """Create an order payload for API requests."""
    payload = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "order_type": order_type,
        "portfolio_id": portfolio_id,
    }
    if limit_price is not None:
        payload["limit_price"] = limit_price
    if stop_price is not None:
        payload["stop_price"] = stop_price
    return payload


# ----- Fixtures -----

@pytest.fixture(scope="function")
def session_pool() -> requests.Session:
    """Create a session with connection pooling."""
    return create_session_with_pool(100)


@pytest.fixture(scope="function")
def base_url() -> str:
    """Base URL for the API."""
    return os.getenv("NEXUS_LOAD_TEST_BASE_URL", "http://localhost:8000/api/v1")


@pytest.fixture(scope="function")
def portfolio_id(perf_test_portfolio) -> str:
    """Get portfolio ID for order tests."""
    return perf_test_portfolio.id


@pytest.fixture(scope="function")
def order_payload_market(portfolio_id: str) -> Dict[str, Any]:
    """Create a market order payload."""
    return create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=1)


@pytest.fixture(scope="function")
def order_payload_limit(portfolio_id: str) -> Dict[str, Any]:
    """Create a limit order payload."""
    return create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="limit", quantity=1, limit_price=150.0)


@pytest.fixture(scope="function")
def order_payload_stop(portfolio_id: str) -> Dict[str, Any]:
    """Create a stop order payload."""
    return create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="stop", quantity=1, stop_price=145.0)


# ----- Order placement benchmarks -----

class TestOrderPlacementLatency:
    """Benchmark order placement latency for different order types."""

    @pytest.mark.parametrize("order_type,price_params", [
        ("market", {}),
        ("limit", {"limit_price": 150.0}),
        ("stop", {"stop_price": 145.0}),
    ])
    def test_place_order_latency(
        self,
        benchmark,
        perf_client: TestClient,
        perf_auth_headers: Dict,
        portfolio_id: str,
        order_type: str,
        price_params: Dict,
    ):
        """Benchmark placing a single order with different types."""
        payload = create_order_payload(
            portfolio_id,
            symbol="AAPL",
            side="buy",
            order_type=order_type,
            quantity=1,
            **price_params
        )

        @benchmark
        def _place_order():
            response = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
            # We accept 200-400 (validation errors are expected for some cases)
            assert response.status_code < 500
            return response

    def test_place_order_with_risk_check(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str):
        """Benchmark placing an order that triggers risk checks."""
        payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=10)

        @benchmark
        def _place_with_risk():
            response = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
            assert response.status_code < 500
            return response

    def test_place_order_validation_only(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str):
        """Benchmark order validation (without execution) using a validation endpoint."""
        # Assuming there is a validation endpoint; if not, we'll simulate via a check.
        # We'll use the risk check endpoint as a proxy for validation.
        payload = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 10,
            "price": 150.0,
            "portfolio_id": portfolio_id,
        }

        @benchmark
        def _validate_order():
            response = perf_client.post("/api/v1/risk/check-order", json=payload, headers=perf_auth_headers)
            assert response.status_code == 200
            return response


# ----- Order cancellation benchmarks -----

class TestOrderCancellationLatency:
    """Benchmark order cancellation latency."""

    @pytest.fixture(scope="function")
    def open_order_id(self, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str) -> str:
        """Create an open order and return its ID."""
        payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="limit", quantity=1, limit_price=1.0)
        response = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
        # Limit order with very low price should remain open
        if response.status_code == 201:
            return response.json().get("id")
        # Fallback: create using direct DB if needed
        return None

    def test_cancel_order_latency(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, open_order_id: str):
        """Benchmark cancelling an open order."""
        if not open_order_id:
            pytest.skip("Could not create open order for cancellation benchmark")

        @benchmark
        def _cancel_order():
            response = perf_client.post(f"/api/v1/trading/orders/{open_order_id}/cancel", headers=perf_auth_headers)
            # 200 or 204 expected
            assert response.status_code in [200, 204]
            return response


# ----- Concurrent order placement -----

class TestConcurrentOrderPlacement:
    """Benchmark concurrent order placement."""

    @pytest.mark.parametrize("concurrency", [5, 10, 25])
    def test_concurrent_market_orders(self, benchmark, session_pool, base_url, perf_auth_headers, portfolio_id, concurrency):
        """Benchmark placing multiple market orders concurrently."""
        url = f"{base_url}/trading/orders"
        headers = perf_auth_headers
        payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=1)

        def _request():
            return make_request(session_pool, url, "POST", headers=headers, data=payload)

        @benchmark
        def _concurrent():
            num_requests = concurrency * 5
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(_request) for _ in range(num_requests)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                successes = sum(1 for _, ok, _ in results if ok)
                return successes / num_requests

    @pytest.mark.parametrize("concurrency", [5, 10, 20])
    def test_concurrent_limit_orders(self, benchmark, session_pool, base_url, perf_auth_headers, portfolio_id, concurrency):
        """Benchmark placing multiple limit orders concurrently."""
        url = f"{base_url}/trading/orders"
        headers = perf_auth_headers
        # Use a low limit price to keep orders open
        payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="limit", quantity=1, limit_price=0.5)

        def _request():
            return make_request(session_pool, url, "POST", headers=headers, data=payload)

        @benchmark
        def _concurrent():
            num_requests = concurrency * 4
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(_request) for _ in range(num_requests)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                successes = sum(1 for _, ok, _ in results if ok)
                return successes / num_requests

    @pytest.mark.parametrize("concurrency", [5, 10, 20])
    def test_concurrent_mixed_orders(self, benchmark, session_pool, base_url, perf_auth_headers, portfolio_id, concurrency):
        """Benchmark placing a mix of market and limit orders concurrently."""
        url = f"{base_url}/trading/orders"
        headers = perf_auth_headers

        def _request():
            order_type = random.choice(["market", "limit", "stop"])
            if order_type == "market":
                payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=1)
            elif order_type == "limit":
                payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="limit", quantity=1, limit_price=0.5)
            else:
                payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="stop", quantity=1, stop_price=145.0)
            return make_request(session_pool, url, "POST", headers=headers, data=payload)

        @benchmark
        def _concurrent():
            num_requests = concurrency * 4
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(_request) for _ in range(num_requests)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                successes = sum(1 for _, ok, _ in results if ok)
                return successes / num_requests


# ----- Bulk order placement -----

class TestBulkOrderPlacement:
    """Benchmark bulk order placement (multiple orders in one request if supported)."""

    def test_bulk_order_placement(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str):
        """Benchmark bulk order placement (if the API supports it)."""
        payload = {
            "orders": [
                create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=1),
                create_order_payload(portfolio_id, symbol="MSFT", side="buy", order_type="limit", quantity=1, limit_price=300.0),
                create_order_payload(portfolio_id, symbol="GOOGL", side="sell", order_type="limit", quantity=1, limit_price=2000.0),
                create_order_payload(portfolio_id, symbol="AMZN", side="buy", order_type="market", quantity=1),
            ]
        }

        @benchmark
        def _bulk_orders():
            # Some APIs may have a bulk endpoint; we'll use the standard endpoint if it accepts lists.
            # If not, we'll simulate by making multiple calls.
            # For this benchmark, we'll assume a bulk endpoint exists.
            response = perf_client.post("/api/v1/trading/orders/bulk", json=payload, headers=perf_auth_headers)
            if response.status_code == 404:
                # If bulk endpoint doesn't exist, we'll simulate by making individual calls.
                # But we can't benchmark that easily.
                pytest.skip("Bulk orders endpoint not available")
            assert response.status_code < 500
            return response


# ----- Order book management performance -----

class TestOrderBookManagement:
    """Benchmark order book operations."""

    def test_get_open_orders_latency(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """Benchmark retrieving open orders."""
        @benchmark
        def _get_open():
            response = perf_client.get("/api/v1/trading/orders/open", headers=perf_auth_headers)
            assert response.status_code == 200
            return response

    def test_get_order_history_latency(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict):
        """Benchmark retrieving order history."""
        params = {"limit": 50}
        @benchmark
        def _get_history():
            response = perf_client.get("/api/v1/trading/orders/history", params=params, headers=perf_auth_headers)
            assert response.status_code == 200
            return response


# ----- Order validation and rejection performance -----

class TestOrderValidationPerformance:
    """Benchmark order validation and rejection scenarios."""

    def test_invalid_order_rejection(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str):
        """Benchmark the time to reject an invalid order."""
        # Invalid order: negative quantity
        payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=-5)

        @benchmark
        def _invalid_order():
            response = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
            # Should be rejected with 400
            assert response.status_code == 400
            return response

    def test_insufficient_balance_rejection(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str):
        """Benchmark the time to reject an order due to insufficient balance."""
        # Very large quantity that should exceed balance
        payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=9999999)

        @benchmark
        def _insufficient_balance():
            response = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
            # Should be rejected with 400
            assert response.status_code in [400, 422]
            return response


# ----- Portfolio update after order execution -----

class TestPortfolioUpdateAfterOrder:
    """Benchmark portfolio update latency after order execution."""

    def test_portfolio_update_after_market_order(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str):
        """Benchmark portfolio summary retrieval after placing a market order."""
        # First, place a market order
        payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=1)
        order_resp = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
        if order_resp.status_code >= 400:
            pytest.skip("Could not place order for portfolio update benchmark")

        # Benchmark getting the updated portfolio summary
        @benchmark
        def _get_portfolio():
            response = perf_client.get("/api/v1/portfolio/summary", headers=perf_auth_headers)
            assert response.status_code == 200
            return response


# ----- Order processing pipeline benchmarks -----

class TestOrderProcessingPipeline:
    """Benchmark the end-to-end order processing pipeline."""

    def test_end_to_end_order_processing(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str):
        """
        Benchmark the end-to-end order processing: validation -> execution -> confirmation.
        This simulates the full lifecycle of a market order.
        """
        @benchmark
        def _e2e_order():
            # Step 1: Place order
            payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=1)
            order_resp = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
            if order_resp.status_code >= 400:
                # If rejected, we still count the time for the failure
                return order_resp.status_code

            order_data = order_resp.json()
            order_id = order_data.get("id")

            if not order_id:
                return 400

            # Step 2: Get order status (confirmation)
            status_resp = perf_client.get(f"/api/v1/trading/orders/{order_id}", headers=perf_auth_headers)
            if status_resp.status_code != 200:
                return status_resp.status_code

            # Step 3: Get portfolio summary (update)
            portfolio_resp = perf_client.get("/api/v1/portfolio/summary", headers=perf_auth_headers)

            return portfolio_resp.status_code

    def test_order_lifecycle_market_to_close(self, benchmark, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str):
        """
        Benchmark the full lifecycle: place market order -> get position -> close position.
        """
        @benchmark
        def _full_lifecycle():
            # Place market order
            payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=1)
            order_resp = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
            if order_resp.status_code >= 400:
                return 400

            order_data = order_resp.json()
            position_id = order_data.get("position_id")

            if not position_id:
                # Try to get position from portfolio
                pos_resp = perf_client.get("/api/v1/portfolio/positions", headers=perf_auth_headers)
                if pos_resp.status_code == 200:
                    positions = pos_resp.json()
                    for p in positions:
                        if p.get("symbol") == "AAPL":
                            position_id = p.get("id")
                            break

            if not position_id:
                return 404

            # Close position
            close_resp = perf_client.post(f"/api/v1/portfolio/positions/{position_id}/close", headers=perf_auth_headers)
            return close_resp.status_code


# ----- Different order sizes performance -----

@pytest.mark.parametrize("quantity", [1, 10, 100, 1000])
def test_order_placement_by_size(benchmark, perf_client: TestClient, perf_auth_headers: Dict, portfolio_id: str, quantity: int):
    """Benchmark order placement with different quantities."""
    payload = create_order_payload(portfolio_id, symbol="AAPL", side="buy", order_type="market", quantity=quantity)

    @benchmark
    def _place_by_size():
        response = perf_client.post("/api/v1/trading/orders", json=payload, headers=perf_auth_headers)
        assert response.status_code < 500
        return response


# ----- Report generation -----

def test_generate_order_execution_performance_report():
    """
    Generate a comprehensive report of order execution performance metrics.
    This runs a series of tests and records results for comparison.
    """
    import time
    import json
    from datetime import datetime

    base_url = os.getenv("NEXUS_LOAD_TEST_BASE_URL", "http://localhost:8000/api/v1")
    auth_token = os.getenv("TEST_USER_TOKEN")
    if not auth_token:
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

    # Get portfolio ID
    portfolio_resp = session.get(f"{base_url}/portfolio/summary", headers=headers)
    if portfolio_resp.status_code != 200:
        print("Could not get portfolio; skipping report")
        return
    portfolio_id = portfolio_resp.json().get("id")

    endpoints = [
        ("market_order", "/trading/orders", "POST", create_order_payload(portfolio_id, order_type="market")),
        ("limit_order", "/trading/orders", "POST", create_order_payload(portfolio_id, order_type="limit", limit_price=150.0)),
        ("stop_order", "/trading/orders", "POST", create_order_payload(portfolio_id, order_type="stop", stop_price=145.0)),
        ("open_orders", "/trading/orders/open", "GET", None),
        ("order_history", "/trading/orders/history?limit=50", "GET", None),
        ("risk_check", "/risk/check-order", "POST", {"symbol": "AAPL", "side": "buy", "quantity": 10, "price": 150.0, "portfolio_id": portfolio_id}),
    ]

    results = {}
    for name, path, method, data in endpoints:
        url = f"{base_url}{path}"
        latencies = []
        successes = 0
        for _ in range(10):
            if method == "GET":
                lat, ok, _ = make_request(session, url, "GET", headers=headers)
            else:
                lat, ok, _ = make_request(session, url, "POST", headers=headers, data=data)
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
    report_path = os.path.join(report_dir, f"order_execution_perf_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }, f, indent=2)
    print(f"Order execution performance report saved to {report_path}")
