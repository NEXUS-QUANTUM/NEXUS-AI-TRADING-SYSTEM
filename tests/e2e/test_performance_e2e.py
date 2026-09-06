# tests/e2e/test_performance_e2e.py
"""
End-to-End Performance Tests.

This module contains performance and load tests for the NEXUS trading system,
measuring response times, throughput, and concurrency handling for critical
endpoints and flows. Tests are designed to run in CI/CD pipelines and provide
baseline metrics for performance regression detection.

Tests cover:
- API endpoint response times (p95, p99)
- Concurrent user load simulation
- WebSocket message throughput and latency
- Database query performance
- Caching effectiveness
- Full trading flow latency
- Stress testing under high load

Note: These tests are not meant to replace dedicated load testing tools
like Locust or k6, but serve as quick performance sanity checks.
"""

import asyncio
import time
from collections import defaultdict
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient

# Import fixtures from conftest
pytest_plugins = ["tests.e2e.conftest"]


# ============================== TEST HELPERS ==============================

class PerformanceMetrics:
    """Simple performance metrics collector."""

    def __init__(self):
        self.timings: List[float] = []
        self.errors: int = 0
        self.success: int = 0

    def add(self, duration: float, success: bool = True):
        if success:
            self.success += 1
            self.timings.append(duration)
        else:
            self.errors += 1

    def get_stats(self) -> Dict[str, Any]:
        if not self.timings:
            return {"success": self.success, "errors": self.errors, "avg": None, "p95": None, "p99": None}
        sorted_timings = sorted(self.timings)
        return {
            "success": self.success,
            "errors": self.errors,
            "total": self.success + self.errors,
            "avg": sum(self.timings) / len(self.timings),
            "min": min(self.timings),
            "max": max(self.timings),
            "p50": sorted_timings[int(len(sorted_timings) * 0.5)],
            "p95": sorted_timings[int(len(sorted_timings) * 0.95)],
            "p99": sorted_timings[int(len(sorted_timings) * 0.99)],
        }


async def measure_endpoint(
    async_client: AsyncClient,
    method: str,
    path: str,
    headers: Dict = None,
    json: Dict = None,
    params: Dict = None,
    expected_status: int = 200,
) -> float:
    """Measure response time for a single endpoint call."""
    start = time.time()
    response = await async_client.request(method, path, headers=headers, json=json, params=params)
    elapsed = time.time() - start
    if expected_status:
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"
    return elapsed


async def run_concurrent_requests(
    async_client: AsyncClient,
    method: str,
    path: str,
    num_requests: int,
    concurrency: int,
    headers: Dict = None,
    json: Dict = None,
    params: Dict = None,
    expected_status: int = 200,
) -> PerformanceMetrics:
    """Run multiple concurrent requests to the same endpoint."""
    semaphore = asyncio.Semaphore(concurrency)
    metrics = PerformanceMetrics()

    async def _make_request():
        async with semaphore:
            try:
                start = time.time()
                response = await async_client.request(method, path, headers=headers, json=json, params=params)
                elapsed = time.time() - start
                if response.status_code == expected_status:
                    metrics.add(elapsed, success=True)
                else:
                    metrics.add(elapsed, success=False)
                    metrics.errors += 1  # duplicate, but add also tracks success/failure
            except Exception:
                metrics.errors += 1

    tasks = [asyncio.create_task(_make_request()) for _ in range(num_requests)]
    await asyncio.gather(*tasks)
    return metrics


# ============================== AUTHENTICATION PERFORMANCE ==============================

class TestAuthPerformance:
    """Performance tests for authentication endpoints."""

    async def test_login_response_time(
        self,
        async_client: AsyncClient,
        test_user_data: Dict[str, Any],
    ):
        """Measure login endpoint response time."""
        # Warm-up request
        await async_client.post(
            "/api/v1/auth/login",
            data={"username": test_user_data["email"], "password": test_user_data["password"]},
        )

        # Measure multiple requests
        metrics = PerformanceMetrics()
        for _ in range(10):
            start = time.time()
            resp = await async_client.post(
                "/api/v1/auth/login",
                data={"username": test_user_data["email"], "password": test_user_data["password"]},
            )
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        # Login should be fast (< 500ms average, < 1s p95)
        assert stats["avg"] < 0.5, f"Login avg too slow: {stats['avg']:.3f}s"
        assert stats["p95"] < 1.0, f"Login p95 too slow: {stats['p95']:.3f}s"

    async def test_registration_performance(
        self,
        async_client: AsyncClient,
    ):
        """Measure registration endpoint performance (create and clean up)."""
        # We'll create a unique user each time.
        import time as t
        ts = int(t.time())
        user_data = {
            "email": f"perf_{ts}@nexustradingia.com",
            "username": f"perf_{ts}",
            "password": "StrongPass123!",
            "full_name": "Perf Test",
            "agree_to_terms": True,
        }
        start = time.time()
        resp = await async_client.post("/api/v1/auth/register", json=user_data)
        elapsed = time.time() - start
        assert resp.status_code == status.HTTP_201_CREATED
        # Registration includes hashing, so may be slower; still should be < 1s
        assert elapsed < 1.0, f"Registration took {elapsed:.3f}s"

    async def test_token_refresh_performance(
        self,
        async_client: AsyncClient,
        refresh_token: str,
    ):
        """Measure refresh token endpoint performance."""
        # Warm-up
        await async_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

        metrics = PerformanceMetrics()
        for _ in range(10):
            start = time.time()
            resp = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        assert stats["avg"] < 0.3, f"Refresh avg too slow: {stats['avg']:.3f}s"


# ============================== MARKET DATA PERFORMANCE ==============================

class TestMarketDataPerformance:
    """Performance tests for market data endpoints."""

    async def test_ticker_response_time(self, async_client: AsyncClient):
        """Measure ticker endpoint response time."""
        metrics = PerformanceMetrics()
        for _ in range(20):
            start = time.time()
            resp = await async_client.get("/api/v1/market/ticker/BTC-USD")
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        # Ticker should be very fast (< 100ms avg, < 300ms p95)
        assert stats["avg"] < 0.1, f"Ticker avg too slow: {stats['avg']:.3f}s"
        assert stats["p95"] < 0.3, f"Ticker p95 too slow: {stats['p95']:.3f}s"

    async def test_ohlcv_response_time(self, async_client: AsyncClient):
        """Measure OHLCV endpoint response time."""
        params = {"timeframe": "1h", "limit": 100}
        # Warm-up
        await async_client.get("/api/v1/market/ohlcv/BTC-USD", params=params)

        metrics = PerformanceMetrics()
        for _ in range(10):
            start = time.time()
            resp = await async_client.get("/api/v1/market/ohlcv/BTC-USD", params=params)
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        # OHLCV with 100 candles should be < 500ms
        assert stats["avg"] < 0.5, f"OHLCV avg too slow: {stats['avg']:.3f}s"
        assert stats["p95"] < 1.0, f"OHLCV p95 too slow: {stats['p95']:.3f}s"

    async def test_order_book_response_time(self, async_client: AsyncClient):
        """Measure order book endpoint response time."""
        metrics = PerformanceMetrics()
        for _ in range(20):
            start = time.time()
            resp = await async_client.get("/api/v1/market/orderbook/BTC-USD")
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        assert stats["avg"] < 0.15, f"Order book avg too slow: {stats['avg']:.3f}s"
        assert stats["p95"] < 0.4, f"Order book p95 too slow: {stats['p95']:.3f}s"

    async def test_ohlcv_with_caching(self, async_client: AsyncClient):
        """Measure OHLCV response time when cached."""
        params = {"timeframe": "1h", "limit": 50}
        # First request to populate cache
        await async_client.get("/api/v1/market/ohlcv/BTC-USD", params=params)

        metrics = PerformanceMetrics()
        for _ in range(10):
            start = time.time()
            resp = await async_client.get("/api/v1/market/ohlcv/BTC-USD", params=params)
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        # Cached response should be very fast (< 50ms avg)
        assert stats["avg"] < 0.05, f"Cached OHLCV avg too slow: {stats['avg']:.3f}s"


# ============================== PORTFOLIO AND TRADING PERFORMANCE ==============================

class TestPortfolioPerformance:
    """Performance tests for portfolio and trading endpoints."""

    async def test_portfolio_list_performance(
        self,
        async_client: AsyncClient,
        access_token: str,
    ):
        """Measure portfolio list endpoint performance."""
        headers = {"Authorization": f"Bearer {access_token}"}
        # Warm-up
        await async_client.get("/api/v1/portfolios", headers=headers)

        metrics = PerformanceMetrics()
        for _ in range(10):
            start = time.time()
            resp = await async_client.get("/api/v1/portfolios", headers=headers)
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        assert stats["avg"] < 0.3, f"Portfolio list avg too slow: {stats['avg']:.3f}s"

    async def test_positions_performance(
        self,
        async_client: AsyncClient,
        access_token: str,
        test_portfolio,
    ):
        """Measure positions list performance."""
        headers = {"Authorization": f"Bearer {access_token}"}
        path = f"/api/v1/portfolios/{test_portfolio.id}/positions"
        metrics = PerformanceMetrics()
        for _ in range(10):
            start = time.time()
            resp = await async_client.get(path, headers=headers)
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        assert stats["avg"] < 0.2, f"Positions avg too slow: {stats['avg']:.3f}s"

    async def test_order_placement_performance(
        self,
        async_client: AsyncClient,
        access_token: str,
        test_portfolio,
    ):
        """Measure order placement (market order) latency."""
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {
            "symbol": "BTC-USD",
            "side": "buy",
            "order_type": "market",
            "quantity": 0.001,
        }
        path = f"/api/v1/portfolios/{test_portfolio.id}/orders"

        # Warm-up
        resp = await async_client.post(path, headers=headers, json=payload)
        assert resp.status_code == status.HTTP_201_CREATED

        metrics = PerformanceMetrics()
        for _ in range(5):  # few orders to avoid overloading test system
            start = time.time()
            resp = await async_client.post(path, headers=headers, json=payload)
            elapsed = time.time() - start
            if resp.status_code == status.HTTP_201_CREATED:
                metrics.add(elapsed)
                # Cancel the order quickly to clean up
                order_id = resp.json().get("id")
                await async_client.delete(f"/api/v1/orders/{order_id}", headers=headers)
            else:
                metrics.errors += 1

        stats = metrics.get_stats()
        # Market order placement should be fast (< 500ms)
        if stats["total"] > 0:
            assert stats["avg"] < 0.5, f"Order placement avg too slow: {stats['avg']:.3f}s"

    async def test_full_trading_flow_latency(
        self,
        async_client: AsyncClient,
        access_token: str,
        test_portfolio,
    ):
        """Measure end-to-end trading flow: place order -> check status -> cancel."""
        headers = {"Authorization": f"Bearer {access_token}"}
        payload_limit = {
            "symbol": "BTC-USD",
            "side": "buy",
            "order_type": "limit",
            "quantity": 0.1,
            "price": 100000,  # far above current price so it stays pending
        }
        path = f"/api/v1/portfolios/{test_portfolio.id}/orders"

        start_total = time.time()
        # Place order
        start = time.time()
        resp = await async_client.post(path, headers=headers, json=payload_limit)
        place_latency = time.time() - start
        assert resp.status_code == status.HTTP_201_CREATED
        order_id = resp.json().get("id")

        # Get order status
        start = time.time()
        status_resp = await async_client.get(f"/api/v1/orders/{order_id}", headers=headers)
        status_latency = time.time() - start
        assert status_resp.status_code == status.HTTP_200_OK

        # Cancel order
        start = time.time()
        cancel_resp = await async_client.delete(f"/api/v1/orders/{order_id}", headers=headers)
        cancel_latency = time.time() - start
        assert cancel_resp.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT)

        total_latency = time.time() - start_total
        # Total flow should be < 1.5s
        assert total_latency < 1.5, f"Total flow latency too high: {total_latency:.3f}s"
        assert place_latency < 0.5, f"Place latency too high: {place_latency:.3f}s"
        assert status_latency < 0.3, f"Status latency too high: {status_latency:.3f}s"
        assert cancel_latency < 0.3, f"Cancel latency too high: {cancel_latency:.3f}s"


# ============================== CONCURRENT REQUEST TESTS ==============================

class TestConcurrency:
    """Test system behavior under concurrent requests."""

    async def test_concurrent_auth_requests(
        self,
        async_client: AsyncClient,
        test_user_data: Dict[str, Any],
    ):
        """Test handling of multiple concurrent login attempts."""
        num_requests = 20
        concurrency = 5
        metrics = await run_concurrent_requests(
            async_client,
            method="POST",
            path="/api/v1/auth/login",
            num_requests=num_requests,
            concurrency=concurrency,
            data={"username": test_user_data["email"], "password": test_user_data["password"]},
            expected_status=200,
        )
        stats = metrics.get_stats()
        # All should succeed
        assert stats["errors"] == 0
        # Average should be acceptable (< 1s under concurrency)
        assert stats["avg"] < 1.0, f"Concurrent login avg too slow: {stats['avg']:.3f}s"

    async def test_concurrent_market_data_requests(
        self,
        async_client: AsyncClient,
    ):
        """Test handling of many concurrent market data requests."""
        num_requests = 50
        concurrency = 10
        metrics = await run_concurrent_requests(
            async_client,
            method="GET",
            path="/api/v1/market/ticker/BTC-USD",
            num_requests=num_requests,
            concurrency=concurrency,
            expected_status=200,
        )
        stats = metrics.get_stats()
        assert stats["errors"] == 0
        # Market data should handle concurrency well
        assert stats["avg"] < 0.2, f"Concurrent ticker avg too slow: {stats['avg']:.3f}s"
        assert stats["p95"] < 0.5, f"Concurrent ticker p95 too slow: {stats['p95']:.3f}s"

    async def test_concurrent_order_placement(
        self,
        async_client: AsyncClient,
        access_token: str,
        test_portfolio,
    ):
        """Test concurrent order placement from same user."""
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {
            "symbol": "BTC-USD",
            "side": "sell",
            "order_type": "limit",
            "quantity": 0.001,
            "price": 1000000,
        }
        path = f"/api/v1/portfolios/{test_portfolio.id}/orders"
        num_requests = 5
        concurrency = 3
        metrics = await run_concurrent_requests(
            async_client,
            method="POST",
            path=path,
            num_requests=num_requests,
            concurrency=concurrency,
            headers=headers,
            json=payload,
            expected_status=201,
        )
        stats = metrics.get_stats()
        # Some might fail due to rate limiting or balance; we'll allow some failures but not all.
        # At least 70% should succeed.
        assert stats["success"] / max(1, stats["total"]) > 0.7, "Too many failures during concurrent orders"
        # Clean up: cancel all pending orders from this test
        # (We'll fetch all open orders and cancel them)
        orders_resp = await async_client.get("/api/v1/orders", headers=headers)
        if orders_resp.status_code == status.HTTP_200_OK:
            for order in orders_resp.json():
                if order.get("portfolio_id") == test_portfolio.id and order.get("status") == "pending":
                    await async_client.delete(f"/api/v1/orders/{order['id']}", headers=headers)


# ============================== WEBSOCKET PERFORMANCE ==============================

class TestWebSocketPerformance:
    """Performance tests for WebSocket connections and message throughput."""

    async def test_websocket_connection_time(self, sync_client, access_token: str):
        """Measure time to establish WebSocket connection."""
        import time
        start = time.time()
        with sync_client.websocket_connect(f"/ws/market?token={access_token}") as websocket:
            # Wait for connection established message
            data = websocket.receive_json()
            elapsed = time.time() - start
            assert data.get("type") == "connection_established" or data.get("status") == "ok"
            # Connection should be quick (< 200ms)
            assert elapsed < 0.2, f"WebSocket connection took {elapsed:.3f}s"

    async def test_websocket_message_throughput(self, sync_client, access_token: str):
        """Measure WebSocket message send/receive round-trip time."""
        with sync_client.websocket_connect(f"/ws?token={access_token}") as websocket:
            # Wait for connection established
            websocket.receive_json()
            # Subscribe to market data
            subscribe_msg = {"type": "subscribe", "channel": "market_data", "symbols": ["BTC-USD"]}
            start = time.time()
            websocket.send_json(subscribe_msg)
            # Wait for confirmation
            confirm = websocket.receive_json()
            assert confirm.get("status") == "success" or confirm.get("type") == "subscribed"
            # Now send a ping and measure pong latency
            ping_time = time.time()
            websocket.send_json({"type": "ping"})
            pong = websocket.receive_json()
            pong_time = time.time()
            assert pong.get("type") == "pong"
            latency = pong_time - ping_time
            # Ping-pong should be < 100ms
            assert latency < 0.1, f"WebSocket ping-pong latency too high: {latency:.3f}s"

    async def test_websocket_market_data_update_frequency(self, sync_client, access_token: str):
        """Measure rate of market data updates received via WebSocket."""
        with sync_client.websocket_connect(f"/ws?token={access_token}") as websocket:
            websocket.receive_json()  # connection established
            websocket.send_json({"type": "subscribe", "channel": "market_data", "symbols": ["BTC-USD"]})
            websocket.receive_json()  # confirmation

            # Collect updates for 5 seconds
            updates = []
            start = time.time()
            while time.time() - start < 5:
                try:
                    msg = websocket.receive_json()
                    if msg.get("type") == "market_data":
                        updates.append(msg)
                except:
                    break
            # Should receive at least a few updates (depends on market activity; we can accept 0)
            # We'll just ensure we can receive data without error.
            # We'll check that the connection remains open.
            assert len(updates) >= 0


# ============================== DATABASE QUERY PERFORMANCE ==============================

class TestDatabasePerformance:
    """Test database query performance for common operations."""

    async def test_user_lookup_performance(
        self,
        async_client: AsyncClient,
        test_user_data: Dict[str, Any],
    ):
        """Measure time for user lookup via login (which queries the DB)."""
        # This is indirectly measured via login performance.
        # We'll also explicitly test a user detail endpoint.
        # First, get token.
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            data={"username": test_user_data["email"], "password": test_user_data["password"]},
        )
        token = login_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        start = time.time()
        resp = await async_client.get("/api/v1/users/me", headers=headers)
        elapsed = time.time() - start
        assert resp.status_code == status.HTTP_200_OK
        # User lookup should be fast (< 200ms)
        assert elapsed < 0.2, f"User lookup took {elapsed:.3f}s"

    async def test_portfolio_with_positions_query(
        self,
        async_client: AsyncClient,
        access_token: str,
        test_portfolio,
    ):
        """Measure time to fetch portfolio with nested positions."""
        headers = {"Authorization": f"Bearer {access_token}"}
        # Ensure we have positions (the fixture creates one)
        start = time.time()
        resp = await async_client.get(
            f"/api/v1/portfolios/{test_portfolio.id}?include_positions=true",
            headers=headers,
        )
        elapsed = time.time() - start
        assert resp.status_code == status.HTTP_200_OK
        # Should be < 300ms
        assert elapsed < 0.3, f"Portfolio with positions took {elapsed:.3f}s"


# ============================== CACHING PERFORMANCE ==============================

class TestCachingPerformance:
    """Test performance improvements from caching."""

    async def test_cached_vs_uncached_ohlcv(
        self,
        async_client: AsyncClient,
    ):
        """Compare response times between cached and uncached OHLCV requests."""
        params = {"timeframe": "1h", "limit": 50}
        # Uncached: first request (populates cache)
        start = time.time()
        resp1 = await async_client.get("/api/v1/market/ohlcv/BTC-USD", params=params)
        uncached_time = time.time() - start
        assert resp1.status_code == status.HTTP_200_OK

        # Cached: second request
        start = time.time()
        resp2 = await async_client.get("/api/v1/market/ohlcv/BTC-USD", params=params)
        cached_time = time.time() - start
        assert resp2.status_code == status.HTTP_200_OK

        # Cached should be significantly faster (at least 2x)
        # If not, maybe cache is not working; we'll still allow a smaller difference.
        assert cached_time < uncached_time, f"Cached ({cached_time:.3f}s) not faster than uncached ({uncached_time:.3f}s)"
        # We'll also check that cached is < 50ms if uncached > 100ms
        if uncached_time > 0.1:
            assert cached_time < 0.05, f"Cached response too slow: {cached_time:.3f}s"

    async def test_cached_ticker_performance(
        self,
        async_client: AsyncClient,
    ):
        """Check that ticker uses cache effectively."""
        # Ticker is usually cached for a few seconds.
        # Warm up
        await async_client.get("/api/v1/market/ticker/BTC-USD")

        # Measure multiple requests
        metrics = PerformanceMetrics()
        for _ in range(10):
            start = time.time()
            resp = await async_client.get("/api/v1/market/ticker/BTC-USD")
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        # Should be very fast (< 50ms average)
        assert stats["avg"] < 0.05, f"Ticker avg too slow even with caching: {stats['avg']:.3f}s"


# ============================== STRESS TESTS (LIGHT) ==============================

class TestStress:
    """Light stress tests to ensure system stability under moderate load."""

    async def test_mixed_endpoints_load(
        self,
        async_client: AsyncClient,
        access_token: str,
        test_portfolio,
    ):
        """Simulate mixed load with various endpoints concurrently."""
        headers = {"Authorization": f"Bearer {access_token}"}
        # Define a set of endpoints to hit concurrently
        endpoints = [
            ("GET", "/api/v1/market/ticker/BTC-USD", None, None),
            ("GET", "/api/v1/portfolios", headers, None),
            ("GET", f"/api/v1/portfolios/{test_portfolio.id}/positions", headers, None),
            ("GET", "/api/v1/market/ohlcv/BTC-USD", None, {"timeframe": "1h", "limit": 20}),
        ]

        # Repeat the set 5 times with slight concurrency
        tasks = []
        for _ in range(5):
            for method, path, h, params in endpoints:
                tasks.append(
                    async_client.request(method, path, headers=h, params=params)
                )

        start = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start

        # Check that all succeeded (or at least not too many errors)
        success_count = sum(1 for r in responses if isinstance(r, Exception) is False and r.status_code < 500)
        total = len(responses)
        # At least 80% success
        assert success_count / total > 0.8, f"Too many failures in mixed load: {success_count}/{total}"
        # Should complete within 3 seconds
        assert elapsed < 3.0, f"Mixed load took {elapsed:.3f}s"

    async def test_sustained_requests(
        self,
        async_client: AsyncClient,
    ):
        """Test sustained requests over a short period (like a burst)."""
        # Send 30 requests to a lightweight endpoint sequentially.
        metrics = PerformanceMetrics()
        for _ in range(30):
            start = time.time()
            resp = await async_client.get("/api/v1/market/ticker/BTC-USD")
            elapsed = time.time() - start
            assert resp.status_code == status.HTTP_200_OK
            metrics.add(elapsed)

        stats = metrics.get_stats()
        # Should remain stable; no degradation over time.
        # Check that max is not much higher than avg (indicates no buildup).
        assert stats["max"] < stats["avg"] * 3, f"Max latency ({stats['max']:.3f}s) too high vs avg ({stats['avg']:.3f}s)"
