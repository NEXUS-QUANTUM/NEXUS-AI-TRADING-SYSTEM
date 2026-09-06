"""
tests/performance/test_websocket_perf.py

NEXUS AI Trading System - WebSocket Performance Tests

This module uses pytest-benchmark to measure the performance of WebSocket
connections, including:

- Connection establishment latency
- Authentication latency (handshake + token verification)
- Subscription latency (subscribing to channels)
- Message throughput (messages per second)
- Concurrent WebSocket connections
- Reconnection latency
- Heartbeat (ping/pong) latency

These benchmarks help ensure the WebSocket layer meets real-time requirements
for streaming market data and order updates.

Usage:
    pytest tests/performance/test_websocket_perf.py -v --benchmark-autosave
    pytest tests/performance/test_websocket_perf.py -v --benchmark-compare

Note: These tests require a running WebSocket server (default on ws://localhost:8000/ws).

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import asyncio
import pytest
import random
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed
import pytest_asyncio

from tests.performance.conftest import (
    perf_client,
    perf_auth_headers,
    perf_test_user,
    perf_test_token,
    perf_test_portfolio,
)


# ----- Helper functions -----

def get_ws_url() -> str:
    """Get WebSocket URL from environment or default."""
    base_url = os.getenv("NEXUS_LOAD_TEST_BASE_URL", "http://localhost:8000")
    # Convert http to ws
    ws_base = base_url.replace("http://", "ws://").replace("https://", "wss://")
    return f"{ws_base}/ws"


def create_auth_message(token: str) -> str:
    """Create authentication message for WebSocket."""
    return json.dumps({"type": "auth", "token": token})


def create_subscribe_message(channel: str, symbol: str = None) -> str:
    """Create subscription message."""
    msg = {"type": "subscribe", "channel": channel}
    if symbol:
        msg["symbol"] = symbol
    return json.dumps(msg)


def create_unsubscribe_message(channel: str, symbol: str = None) -> str:
    """Create unsubscribe message."""
    msg = {"type": "unsubscribe", "channel": channel}
    if symbol:
        msg["symbol"] = symbol
    return json.dumps(msg)


async def connect_and_authenticate(ws_url: str, token: str, timeout: float = 5.0) -> websockets.WebSocketClientProtocol:
    """
    Connect to WebSocket and authenticate.
    Returns the websocket object after successful auth.
    """
    websocket = await asyncio.wait_for(
        websockets.connect(ws_url, close_timeout=2),
        timeout=timeout
    )
    # Send auth message
    await websocket.send(create_auth_message(token))
    # Wait for auth response
    response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
    data = json.loads(response)
    if data.get("type") != "auth_success":
        raise RuntimeError(f"Authentication failed: {data}")
    return websocket


async def measure_message_throughput(websocket, num_messages: int, timeout: float = 10.0) -> float:
    """
    Measure throughput (messages per second) by receiving messages.
    """
    received = 0
    start = time.perf_counter()
    try:
        while received < num_messages:
            await asyncio.wait_for(websocket.recv(), timeout=timeout)
            received += 1
    except asyncio.TimeoutError:
        pass
    elapsed = time.perf_counter() - start
    return received / elapsed if elapsed > 0 else 0


# ----- Fixtures -----

@pytest.fixture(scope="function")
def ws_url() -> str:
    """WebSocket URL for tests."""
    return get_ws_url()


@pytest.fixture(scope="function")
def auth_token(perf_test_token) -> str:
    """Authentication token for WebSocket tests."""
    return perf_test_token


# ----- WebSocket connection benchmarks -----

@pytest.mark.asyncio
class TestWebSocketConnection:
    """Benchmark WebSocket connection and authentication latency."""

    @pytest.mark.parametrize("num_connections", [1, 5, 10])
    def test_connection_latency(self, benchmark, ws_url: str, auth_token: str, num_connections: int):
        """
        Benchmark WebSocket connection establishment and authentication.
        This test uses asyncio to measure the time to open multiple connections.
        """
        async def _connect_and_auth():
            websocket = await connect_and_authenticate(ws_url, auth_token)
            await websocket.close()
            return True

        # Use benchmark to measure the time for a single connection (or multiple)
        # Since benchmark doesn't support async directly, we'll use a wrapper.
        # We'll use the benchmark fixture with a sync wrapper that runs the async function.
        # Another approach: use asyncio.run() inside the benchmarked function.
        # We'll create a sync function that runs the async code.

        @benchmark
        def _benchmark_connection():
            # Run the async connection in a new event loop for each benchmark iteration
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                for _ in range(num_connections):
                    loop.run_until_complete(_connect_and_auth())
            finally:
                loop.close()

        # We also need to ensure that the benchmark function returns something.
        # The benchmark will report the total time for num_connections.
        # For a single connection, we get the latency per connection.

    @pytest.mark.asyncio
    async def test_single_connection_auth_latency(self, benchmark, ws_url: str, auth_token: str):
        """
        Benchmark the time from connection open to authentication completion.
        This is a more precise benchmark using async directly with benchmark.
        """
        # We'll use a manual timing within the benchmarked function.
        # Since benchmark doesn't handle async, we'll use a sync wrapper.
        # However, we can use benchmark.pedantic with a sync wrapper.

        def _sync_connect():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                start = time.perf_counter()
                websocket = loop.run_until_complete(connect_and_authenticate(ws_url, auth_token))
                loop.run_until_complete(websocket.close())
                elapsed = time.perf_counter() - start
                return elapsed
            finally:
                loop.close()

        @benchmark
        def _benchmark_auth():
            return _sync_connect()


# ----- WebSocket subscription benchmarks -----

@pytest.mark.asyncio
class TestWebSocketSubscription:
    """Benchmark WebSocket subscription and unsubscription latency."""

    @pytest.fixture(scope="function")
    async def authenticated_websocket(self, ws_url: str, auth_token: str):
        """Create an authenticated WebSocket connection for tests."""
        websocket = await connect_and_authenticate(ws_url, auth_token)
        yield websocket
        await websocket.close()

    @pytest.mark.asyncio
    async def test_subscribe_latency(self, benchmark, authenticated_websocket):
        """Benchmark the latency of subscribing to a channel."""
        def _sync_subscribe():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                start = time.perf_counter()
                # Send subscribe message
                loop.run_until_complete(authenticated_websocket.send(
                    create_subscribe_message("market_data", "AAPL")
                ))
                # Wait for confirmation
                resp = loop.run_until_complete(
                    asyncio.wait_for(authenticated_websocket.recv(), timeout=2.0)
                )
                elapsed = time.perf_counter() - start
                # Parse to verify
                data = json.loads(resp)
                assert data.get("type") == "subscribe_success"
                return elapsed
            finally:
                loop.close()

        @benchmark
        def _benchmark_subscribe():
            return _sync_subscribe()

        # Cleanup: unsubscribe
        await authenticated_websocket.send(create_unsubscribe_message("market_data", "AAPL"))
        await authenticated_websocket.recv()

    @pytest.mark.asyncio
    async def test_unsubscribe_latency(self, benchmark, authenticated_websocket):
        """Benchmark the latency of unsubscribing from a channel."""
        # First subscribe
        await authenticated_websocket.send(create_subscribe_message("market_data", "AAPL"))
        await authenticated_websocket.recv()  # consume confirmation

        def _sync_unsubscribe():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                start = time.perf_counter()
                loop.run_until_complete(authenticated_websocket.send(
                    create_unsubscribe_message("market_data", "AAPL")
                ))
                resp = loop.run_until_complete(
                    asyncio.wait_for(authenticated_websocket.recv(), timeout=2.0)
                )
                elapsed = time.perf_counter() - start
                data = json.loads(resp)
                assert data.get("type") == "unsubscribe_success"
                return elapsed
            finally:
                loop.close()

        @benchmark
        def _benchmark_unsubscribe():
            return _sync_unsubscribe()


# ----- WebSocket message throughput -----

@pytest.mark.asyncio
class TestWebSocketThroughput:
    """Benchmark message throughput for market data streaming."""

    @pytest.fixture(scope="function")
    async def authenticated_websocket(self, ws_url: str, auth_token: str):
        websocket = await connect_and_authenticate(ws_url, auth_token)
        yield websocket
        await websocket.close()

    @pytest.mark.asyncio
    async def test_market_data_throughput(self, benchmark, authenticated_websocket):
        """Benchmark the rate of receiving market data messages after subscription."""
        # Subscribe to market data
        await authenticated_websocket.send(create_subscribe_message("market_data", "AAPL"))
        await authenticated_websocket.recv()  # confirmation

        # Measure throughput for a fixed number of messages
        # We'll need to receive a certain number of messages (e.g., 100)
        # If the server is not actively sending, we may need to wait.
        # For a realistic test, we can also send a request for historical data,
        # but the WebSocket server should push updates.
        # We'll receive messages for a limited duration (e.g., 5 seconds) and compute throughput.
        def _sync_throughput():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                num_messages = 50
                start = time.perf_counter()
                count = 0
                try:
                    while count < num_messages:
                        msg = loop.run_until_complete(
                            asyncio.wait_for(authenticated_websocket.recv(), timeout=5.0)
                        )
                        count += 1
                except asyncio.TimeoutError:
                    pass
                elapsed = time.perf_counter() - start
                return count / elapsed if elapsed > 0 else 0
            finally:
                loop.close()

        @benchmark
        def _benchmark_throughput():
            return _sync_throughput()

        # Unsubscribe
        await authenticated_websocket.send(create_unsubscribe_message("market_data", "AAPL"))
        await authenticated_websocket.recv()


# ----- Concurrent WebSocket connections -----

@pytest.mark.asyncio
class TestWebSocketConcurrency:
    """Benchmark WebSocket performance under concurrent connections."""

    @pytest.mark.parametrize("num_connections", [5, 10, 25])
    async def test_concurrent_connections(self, ws_url: str, auth_token: str, num_connections: int):
        """
        Test the performance of multiple concurrent WebSocket connections.
        Measure the time to establish all connections and the total throughput.
        """
        async def connect_and_subscribe(ws_url, token):
            ws = await connect_and_authenticate(ws_url, token)
            await ws.send(create_subscribe_message("market_data", "AAPL"))
            await ws.recv()  # confirmation
            return ws

        start = time.perf_counter()
        websockets_list = []
        try:
            # Establish all connections concurrently
            tasks = [asyncio.create_task(connect_and_subscribe(ws_url, auth_token))
                     for _ in range(num_connections)]
            done, pending = await asyncio.wait(tasks, timeout=10.0)
            for t in done:
                websockets_list.append(t.result())

            elapsed = time.perf_counter() - start
            connections_per_sec = len(websockets_list) / elapsed if elapsed > 0 else 0
            print(f"\nConcurrent {num_connections} connections: {connections_per_sec:.2f} conn/s, total {elapsed:.2f}s")

            # Measure throughput: each connection receives some messages (or just measure time)
            # For a simple test, we'll just receive one message per connection (if available)
            # But that may not be realistic. We'll just count successful connections.
            # We can also test message throughput across all connections.
            # We'll receive a few messages from each connection.
            async def receive_some(ws, count=5):
                received = 0
                try:
                    for _ in range(count):
                        await asyncio.wait_for(ws.recv(), timeout=2.0)
                        received += 1
                except asyncio.TimeoutError:
                    pass
                return received

            receive_tasks = [receive_some(ws, 3) for ws in websockets_list]
            results = await asyncio.gather(*receive_tasks)
            total_received = sum(results)
            total_throughput = total_received / elapsed if elapsed > 0 else 0
            print(f"Total messages received: {total_received}, throughput: {total_throughput:.2f} msg/s")

        finally:
            # Clean up
            for ws in websockets_list:
                await ws.close()

        # We'll assert at least a minimum number of successful connections
        assert len(websockets_list) >= num_connections * 0.8, "Too many failed connections"


# ----- Heartbeat latency -----

@pytest.mark.asyncio
class TestWebSocketHeartbeat:
    """Benchmark heartbeat (ping/pong) latency."""

    @pytest.fixture(scope="function")
    async def authenticated_websocket(self, ws_url: str, auth_token: str):
        websocket = await connect_and_authenticate(ws_url, auth_token)
        yield websocket
        await websocket.close()

    @pytest.mark.asyncio
    async def test_ping_pong_latency(self, benchmark, authenticated_websocket):
        """
        Benchmark the round-trip time of WebSocket ping/pong.
        """
        def _sync_ping():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                start = time.perf_counter()
                # Send ping
                loop.run_until_complete(authenticated_websocket.send(json.dumps({"type": "ping"})))
                # Wait for pong
                loop.run_until_complete(
                    asyncio.wait_for(authenticated_websocket.recv(), timeout=2.0)
                )
                elapsed = time.perf_counter() - start
                return elapsed
            finally:
                loop.close()

        @benchmark
        def _benchmark_ping():
            return _sync_ping()


# ----- Report generation -----

def test_generate_websocket_performance_report():
    """
    Generate a comprehensive report of WebSocket performance metrics.
    This runs a series of tests and records results for comparison.
    """
    import time
    import json
    from datetime import datetime
    import asyncio

    ws_url = get_ws_url()
    token = os.getenv("TEST_USER_TOKEN")
    if not token:
        # Try to get a token via login
        import requests
        base_url = os.getenv("NEXUS_LOAD_TEST_BASE_URL", "http://localhost:8000")
        login_resp = requests.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": "test@nexusquantum.com", "password": "Test@123"}
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
        else:
            print("Could not get auth token; skipping WebSocket performance report")
            return

    results = {}

    async def run_tests():
        # Test 1: Connection + Auth latency (average of 5 connections)
        latencies = []
        for _ in range(5):
            start = time.perf_counter()
            ws = await connect_and_authenticate(ws_url, token)
            await ws.close()
            latencies.append(time.perf_counter() - start)
        results["connection_auth_avg_ms"] = (sum(latencies) / len(latencies)) * 1000

        # Test 2: Subscribe latency
        ws = await connect_and_authenticate(ws_url, token)
        start = time.perf_counter()
        await ws.send(create_subscribe_message("market_data", "AAPL"))
        await ws.recv()
        results["subscribe_latency_ms"] = (time.perf_counter() - start) * 1000
        await ws.close()

        # Test 3: Unsubscribe latency
        ws = await connect_and_authenticate(ws_url, token)
        await ws.send(create_subscribe_message("market_data", "AAPL"))
        await ws.recv()
        start = time.perf_counter()
        await ws.send(create_unsubscribe_message("market_data", "AAPL"))
        await ws.recv()
        results["unsubscribe_latency_ms"] = (time.perf_counter() - start) * 1000
        await ws.close()

        # Test 4: Throughput (connect, subscribe, receive 10 messages)
        # We'll do this for a duration and count messages.
        ws = await connect_and_authenticate(ws_url, token)
        await ws.send(create_subscribe_message("market_data", "AAPL"))
        await ws.recv()
        start = time.perf_counter()
        count = 0
        try:
            while count < 20:
                await asyncio.wait_for(ws.recv(), timeout=5.0)
                count += 1
        except asyncio.TimeoutError:
            pass
        elapsed = time.perf_counter() - start
        results["throughput_msg_per_sec"] = count / elapsed if elapsed > 0 else 0
        await ws.close()

        # Test 5: Concurrent connections (10 connections)
        async def connect_and_subscribe():
            ws = await connect_and_authenticate(ws_url, token)
            await ws.send(create_subscribe_message("market_data", "AAPL"))
            await ws.recv()
            return ws

        start = time.perf_counter()
        tasks = [asyncio.create_task(connect_and_subscribe()) for _ in range(10)]
        done, _ = await asyncio.wait(tasks, timeout=10.0)
        websockets_list = [t.result() for t in done]
        elapsed = time.perf_counter() - start
        results["concurrent_10_connections_time_ms"] = elapsed * 1000
        results["concurrent_10_success_rate"] = len(websockets_list) / 10
        for ws in websockets_list:
            await ws.close()

    # Run the async test suite
    asyncio.run(run_tests())

    print("\n" + "="*60)
    print("WEBSOCKET PERFORMANCE REPORT")
    print("="*60)
    for key, value in results.items():
        if isinstance(value, float):
            print(f"{key:30s} {value:10.2f}")
        else:
            print(f"{key:30s} {value}")
    print("="*60)

    # Save report
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"websocket_perf_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }, f, indent=2)
    print(f"WebSocket performance report saved to {report_path}")
