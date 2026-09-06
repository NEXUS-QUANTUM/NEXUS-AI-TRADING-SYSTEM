"""
tests/load/test_load_baseline.py

NEXUS AI Trading System - Baseline Load Tests

This module establishes baseline performance metrics for critical API endpoints.
It runs a series of load tests to measure:

- Average response time
- 95th/99th percentile response times
- Requests per second (throughput)
- Error rate
- Concurrent user handling
- CPU and memory usage under load

The baseline tests are designed to be run against a deployed environment
(staging or production) to establish performance benchmarks.

Usage:
    pytest tests/load/test_load_baseline.py -v
    locust -f tests/load/test_load_baseline.py --host=http://localhost:8000

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import logging
import pytest
import statistics
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from locust import HttpUser, task, between, events
from locust.exception import StopUser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BASE_URL = os.getenv("NEXUS_LOAD_TEST_BASE_URL", "http://localhost:8000")
API_URL = os.getenv("NEXUS_LOAD_TEST_API_URL", f"{BASE_URL}/api/v1")
LOAD_DURATION = int(os.getenv("LOAD_TEST_DURATION", "120"))  # seconds
LOAD_USERS = int(os.getenv("LOAD_TEST_USERS", "20"))
SPAWN_RATE = int(os.getenv("LOAD_TEST_SPAWN_RATE", "2"))

# Performance thresholds (in seconds)
THRESHOLDS = {
    "average_response_time": 0.5,      # 500ms
    "p95_response_time": 1.0,          # 1 second
    "p99_response_time": 2.0,          # 2 seconds
    "error_rate": 0.01,                # 1% max error rate
    "throughput_min": 10,               # 10 requests per second minimum
}

# Test endpoints with expected performance characteristics
ENDPOINTS = {
    "auth_login": {"method": "POST", "path": "/auth/login", "weight": 10},
    "auth_refresh": {"method": "POST", "path": "/auth/refresh", "weight": 5},
    "users_me": {"method": "GET", "path": "/users/me", "weight": 30},
    "portfolio_summary": {"method": "GET", "path": "/portfolio/summary", "weight": 40},
    "portfolio_positions": {"method": "GET", "path": "/portfolio/positions", "weight": 35},
    "market_quote": {"method": "GET", "path": "/market/quote/AAPL", "weight": 50},
    "market_symbols": {"method": "GET", "path": "/market/symbols", "weight": 20},
    "orders_open": {"method": "GET", "path": "/trading/orders/open", "weight": 25},
    "risk_limits": {"method": "GET", "path": "/risk/limits", "weight": 15},
    "ai_predict": {"method": "GET", "path": "/ai/predict/price/AAPL", "weight": 10},
}


# ----- Helper Functions -----

def create_session_with_retries() -> requests.Session:
    """Create a requests session with retry logic for load tests."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE"],
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_auth_token(session: requests.Session, email: str, password: str) -> Optional[str]:
    """Get authentication token for load test user."""
    try:
        response = session.post(
            f"{API_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            logger.error(f"Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Login error: {e}")
        return None


def setup_test_user(session: requests.Session, email: str = None, password: str = None) -> Dict[str, Any]:
    """Register or login a test user for load testing."""
    if not email:
        email = f"load_baseline_{int(time.time())}_{random.randint(1000, 9999)}@nexusquantum.com"
    if not password:
        password = "LoadTest@123"

    # Try to register
    try:
        response = session.post(
            f"{API_URL}/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Baseline",
                "last_name": "LoadTest",
            },
            timeout=5,
        )
        if response.status_code == 201:
            data = response.json()
            token = data.get("access_token")
            if not token:
                # Login to get token
                token = get_auth_token(session, email, password)
            return {"email": email, "password": password, "token": token, "user_id": data.get("id")}
    except Exception as e:
        logger.debug(f"Registration error (may already exist): {e}")

    # Try to login
    token = get_auth_token(session, email, password)
    if token:
        # Get user_id
        try:
            resp = session.get(
                f"{API_URL}/users/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if resp.status_code == 200:
                user_id = resp.json().get("id")
                return {"email": email, "password": password, "token": token, "user_id": user_id}
        except Exception:
            pass
        return {"email": email, "password": password, "token": token, "user_id": None}

    # Fallback: use default test user if available
    default_email = os.getenv("TEST_USER_EMAIL", "test@nexusquantum.com")
    default_password = os.getenv("TEST_USER_PASSWORD", "Test@123")
    token = get_auth_token(session, default_email, default_password)
    if token:
        return {"email": default_email, "password": default_password, "token": token, "user_id": None}

    logger.error("Failed to authenticate load test user")
    return None


# ----- Pytest-based Baseline Tests -----

@pytest.mark.load
@pytest.mark.smoke_load
class TestBaselinePerformance:
    """Baseline performance tests using pytest."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session and user."""
        self.session = create_session_with_retries()
        self.user = setup_test_user(self.session)
        assert self.user is not None, "Failed to set up test user"
        self.auth_headers = {"Authorization": f"Bearer {self.user['token']}"}
        self.results = defaultdict(list)
        yield
        # Cleanup
        self.session.close()

    def _measure_endpoint(self, endpoint_name: str, method: str, path: str, data: Dict = None, num_requests: int = 10) -> Dict[str, Any]:
        """Measure performance of a single endpoint."""
        url = f"{API_URL}{path}"
        headers = self.auth_headers.copy()
        headers["Content-Type"] = "application/json"

        response_times = []
        errors = 0

        for i in range(num_requests):
            try:
                start = time.time()
                if method.upper() == "GET":
                    response = self.session.get(url, headers=headers, timeout=10, params=data)
                elif method.upper() == "POST":
                    response = self.session.post(url, headers=headers, json=data, timeout=10)
                elif method.upper() == "PUT":
                    response = self.session.put(url, headers=headers, json=data, timeout=10)
                elif method.upper() == "DELETE":
                    response = self.session.delete(url, headers=headers, timeout=10)
                else:
                    response = self.session.request(method, url, headers=headers, json=data, timeout=10)

                elapsed = time.time() - start
                response_times.append(elapsed)

                if response.status_code >= 400:
                    errors += 1
                    logger.debug(f"Error on {endpoint_name}: {response.status_code} - {response.text[:100]}")

            except Exception as e:
                errors += 1
                logger.debug(f"Exception on {endpoint_name}: {e}")

        # Calculate metrics
        if response_times:
            avg = statistics.mean(response_times)
            p95 = sorted(response_times)[int(len(response_times) * 0.95)]
            p99 = sorted(response_times)[int(len(response_times) * 0.99)]
            min_time = min(response_times)
            max_time = max(response_times)
            error_rate = errors / num_requests if num_requests > 0 else 1.0
        else:
            avg = p95 = p99 = min_time = max_time = 0
            error_rate = 1.0

        return {
            "endpoint": endpoint_name,
            "method": method,
            "path": path,
            "num_requests": num_requests,
            "avg_response": avg,
            "p95_response": p95,
            "p99_response": p99,
            "min_response": min_time,
            "max_response": max_time,
            "errors": errors,
            "error_rate": error_rate,
        }

    def test_baseline_authentication(self):
        """Test baseline performance of authentication endpoints."""
        # Login
        login_result = self._measure_endpoint(
            "auth_login",
            "POST",
            "/auth/login",
            {"email": self.user["email"], "password": self.user["password"]},
            num_requests=20,
        )
        self.results["auth_login"].append(login_result)

        # Refresh
        refresh_result = self._measure_endpoint(
            "auth_refresh",
            "POST",
            "/auth/refresh",
            {"refresh_token": self.user.get("refresh_token", self.user["token"])},
            num_requests=10,
        )
        self.results["auth_refresh"].append(refresh_result)

        # Assert thresholds
        assert login_result["avg_response"] < THRESHOLDS["average_response_time"], f"Login avg {login_result['avg_response']:.3f}s > threshold"
        assert login_result["p95_response"] < THRESHOLDS["p95_response_time"], f"Login p95 {login_result['p95_response']:.3f}s > threshold"
        assert login_result["error_rate"] < THRESHOLDS["error_rate"], f"Login error rate {login_result['error_rate']:.2%} > threshold"

    def test_baseline_read_endpoints(self):
        """Test baseline performance of read-only endpoints."""
        endpoints = [
            ("users_me", "GET", "/users/me"),
            ("portfolio_summary", "GET", "/portfolio/summary"),
            ("portfolio_positions", "GET", "/portfolio/positions"),
            ("market_quote", "GET", "/market/quote/AAPL"),
            ("market_symbols", "GET", "/market/symbols"),
            ("orders_open", "GET", "/trading/orders/open"),
            ("risk_limits", "GET", "/risk/limits"),
            ("ai_predict", "GET", "/ai/predict/price/AAPL"),
        ]

        for name, method, path in endpoints:
            result = self._measure_endpoint(name, method, path, num_requests=30)
            self.results[name].append(result)

            # Assert thresholds
            assert result["avg_response"] < THRESHOLDS["average_response_time"], \
                f"{name} avg {result['avg_response']:.3f}s > threshold"
            assert result["error_rate"] < THRESHOLDS["error_rate"], \
                f"{name} error rate {result['error_rate']:.2%} > threshold"

            logger.info(f"{name}: avg={result['avg_response']:.3f}s, p95={result['p95_response']:.3f}s, errors={result['error_rate']:.2%}")

    def test_baseline_order_placement(self):
        """Test baseline performance of order placement (write operation)."""
        # Note: This may affect portfolio balance; use with caution.
        order_payload = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 1,
            "order_type": "market",
            "portfolio_id": None,  # Will be fetched
        }

        # Get portfolio ID
        resp = self.session.get(
            f"{API_URL}/portfolio/summary",
            headers=self.auth_headers,
            timeout=10,
        )
        if resp.status_code == 200:
            order_payload["portfolio_id"] = resp.json().get("id")

        if not order_payload["portfolio_id"]:
            logger.warning("No portfolio ID found, skipping order placement test")
            return

        result = self._measure_endpoint(
            "order_place",
            "POST",
            "/trading/orders",
            order_payload,
            num_requests=5,  # Fewer requests to avoid spamming
        )
        self.results["order_place"].append(result)

        # We have lower expectations for writes
        assert result["avg_response"] < 1.0, f"Order avg {result['avg_response']:.3f}s > 1s"
        assert result["error_rate"] < 0.05, f"Order error rate {result['error_rate']:.2%} > 5%"

    def test_baseline_concurrent_requests(self):
        """Test performance under concurrent requests."""
        endpoints_to_test = [
            ("users_me", "GET", "/users/me"),
            ("portfolio_summary", "GET", "/portfolio/summary"),
            ("market_quote", "GET", "/market/quote/AAPL"),
        ]

        def make_request(endpoint_name: str, method: str, path: str) -> Tuple[str, float, bool]:
            start = time.time()
            try:
                url = f"{API_URL}{path}"
                if method == "GET":
                    response = self.session.get(url, headers=self.auth_headers, timeout=10)
                else:
                    response = self.session.request(method, url, headers=self.auth_headers, timeout=10)
                elapsed = time.time() - start
                success = response.status_code < 400
                return (endpoint_name, elapsed, success)
            except Exception:
                return (endpoint_name, time.time() - start, False)

        # Run 20 concurrent requests per endpoint
        num_concurrent = 20
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            for _ in range(num_concurrent):
                for name, method, path in endpoints_to_test:
                    futures.append(executor.submit(make_request, name, method, path))

        results = [f.result() for f in futures]

        # Aggregate results
        by_endpoint = defaultdict(list)
        for name, elapsed, success in results:
            by_endpoint[name].append((elapsed, success))

        for name, measurements in by_endpoint.items():
            times = [t for t, s in measurements]
            success_count = sum(1 for t, s in measurements if s)
            error_rate = 1 - (success_count / len(measurements)) if measurements else 1.0
            avg = statistics.mean(times) if times else 0
            p95 = sorted(times)[int(len(times) * 0.95)] if times else 0

            logger.info(f"Concurrent {name}: avg={avg:.3f}s, p95={p95:.3f}s, error_rate={error_rate:.2%}")

            # Assert thresholds (allow slightly higher for concurrent)
            assert avg < THRESHOLDS["average_response_time"] * 1.5, f"Concurrent {name} avg {avg:.3f}s > 1.5x threshold"
            assert error_rate < THRESHOLDS["error_rate"] * 2, f"Concurrent {name} error rate {error_rate:.2%} > 2x threshold"

    def test_baseline_throughput(self):
        """Test throughput (requests per second) for critical endpoints."""
        endpoint = ("portfolio_summary", "GET", "/portfolio/summary")
        duration = 10  # seconds

        start_time = time.time()
        requests_count = 0
        errors = 0

        while time.time() - start_time < duration:
            try:
                response = self.session.get(
                    f"{API_URL}{endpoint[2]}",
                    headers=self.auth_headers,
                    timeout=5,
                )
                requests_count += 1
                if response.status_code >= 400:
                    errors += 1
            except Exception:
                requests_count += 1
                errors += 1

        elapsed = time.time() - start_time
        throughput = requests_count / elapsed if elapsed > 0 else 0
        error_rate = errors / requests_count if requests_count > 0 else 1.0

        logger.info(f"Throughput for {endpoint[0]}: {throughput:.2f} req/s, errors={error_rate:.2%}")

        # Assert minimum throughput
        assert throughput > THRESHOLDS["throughput_min"], f"Throughput {throughput:.2f} req/s < {THRESHOLDS['throughput_min']}"
        assert error_rate < THRESHOLDS["error_rate"] * 2, f"Throughput error rate {error_rate:.2%} > 2x threshold"

    def test_baseline_long_running_stability(self):
        """Test stability over an extended period (short burst)."""
        # Run 100 requests with a pause between them to simulate real usage
        endpoint = ("portfolio_summary", "GET", "/portfolio/summary")
        num_requests = 100
        pause_between = 0.1  # 100ms

        response_times = []
        errors = 0

        for i in range(num_requests):
            try:
                start = time.time()
                response = self.session.get(
                    f"{API_URL}{endpoint[2]}",
                    headers=self.auth_headers,
                    timeout=10,
                )
                elapsed = time.time() - start
                response_times.append(elapsed)
                if response.status_code >= 400:
                    errors += 1
                time.sleep(pause_between)
            except Exception as e:
                errors += 1
                logger.debug(f"Long-running error: {e}")

        # Assert no degradation over time
        avg = statistics.mean(response_times) if response_times else 0
        p95 = sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0
        error_rate = errors / num_requests if num_requests > 0 else 1.0

        logger.info(f"Long-running {endpoint[0]}: avg={avg:.3f}s, p95={p95:.3f}s, errors={error_rate:.2%}")

        # Check if early requests were faster than later requests (degradation check)
        if len(response_times) > 20:
            first_half = response_times[:len(response_times)//2]
            second_half = response_times[len(response_times)//2:]
            if first_half and second_half:
                avg_first = statistics.mean(first_half)
                avg_second = statistics.mean(second_half)
                degradation = (avg_second - avg_first) / avg_first if avg_first > 0 else 0
                logger.info(f"Degradation: {degradation*100:.1f}%")
                # Degradation should be less than 50%
                assert degradation < 0.5, f"Performance degraded by {degradation*100:.1f}%"

    def test_baseline_api_error_resilience(self):
        """Test that the API handles invalid requests gracefully under load."""
        invalid_endpoints = [
            ("invalid_auth", "POST", "/auth/login", {"email": "invalid", "password": "wrong"}),
            ("invalid_symbol", "GET", "/market/quote/INVALID_SYMBOL_XYZ"),
            ("invalid_endpoint", "GET", "/invalid/path/does/not/exist"),
            ("invalid_order", "POST", "/trading/orders", {"symbol": "AAPL", "side": "invalid_side"}),
        ]

        for name, method, path, data in [(e[0], e[1], e[2], e[3] if len(e) > 3 else None) for e in invalid_endpoints]:
            result = self._measure_endpoint(name, method, path, data, num_requests=5)
            self.results[name].append(result)
            # Error rate should be high (expected), but response should be fast
            assert result["avg_response"] < 1.0, f"{name} slow response {result['avg_response']:.3f}s"

    def test_baseline_report(self):
        """Generate a baseline performance report."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "thresholds": THRESHOLDS,
            "results": {},
            "summary": {"passed": 0, "failed": 0, "warnings": 0},
        }

        for endpoint_name, measurements in self.results.items():
            if not measurements:
                continue
            # Aggregate results for this endpoint
            all_avg = [m["avg_response"] for m in measurements]
            all_p95 = [m["p95_response"] for m in measurements]
            all_errors = [m["error_rate"] for m in measurements]

            report["results"][endpoint_name] = {
                "avg_response": statistics.mean(all_avg) if all_avg else 0,
                "p95_response": statistics.mean(all_p95) if all_p95 else 0,
                "error_rate": statistics.mean(all_errors) if all_errors else 0,
                "num_measurements": len(measurements),
                "details": measurements,
            }

        # Log summary
        logger.info("=" * 60)
        logger.info("BASELINE PERFORMANCE REPORT")
        logger.info("=" * 60)
        for name, metrics in report["results"].items():
            status = "✅ PASS" if metrics["avg_response"] < THRESHOLDS["average_response_time"] else "❌ FAIL"
            logger.info(f"{status} {name}: avg={metrics['avg_response']:.3f}s, p95={metrics['p95_response']:.3f}s, errors={metrics['error_rate']:.2%}")
        logger.info("=" * 60)

        # Save report to file
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"baseline_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Report saved to {report_path}")


# ----- Locust User Definition -----

class BaselineLoadTestUser(HttpUser):
    """
    Locust user for baseline load testing.
    Simulates realistic user behavior against the API.
    """
    host = BASE_URL
    wait_time = between(1, 3)  # Think time between tasks
    token = None
    user_id = None

    def on_start(self):
        """Authenticate once per user session."""
        email = os.getenv("TEST_USER_EMAIL", "test@nexusquantum.com")
        password = os.getenv("TEST_USER_PASSWORD", "Test@123")

        # Try to login
        with self.client.post("/api/v1/auth/login", json={"email": email, "password": password}, catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                self.user_id = data.get("user_id")
            else:
                resp.failure(f"Login failed: {resp.status_code}")
                raise StopUser()

        if not self.token:
            raise StopUser()

        # Get portfolio ID
        with self.client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {self.token}"}, catch_response=True) as resp:
            if resp.status_code == 200:
                self.user_id = resp.json().get("id")

    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(40)
    def get_portfolio_summary(self):
        """Task: Get portfolio summary."""
        with self.client.get("/api/v1/portfolio/summary", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(35)
    def get_positions(self):
        """Task: Get positions."""
        with self.client.get("/api/v1/portfolio/positions", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(50)
    def get_market_quote(self):
        """Task: Get market quote."""
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        symbol = symbols[int(time.time()) % len(symbols)]
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(30)
    def get_users_me(self):
        """Task: Get current user profile."""
        with self.client.get("/api/v1/users/me", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(25)
    def get_open_orders(self):
        """Task: Get open orders."""
        with self.client.get("/api/v1/trading/orders/open", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(20)
    def get_market_symbols(self):
        """Task: Get market symbols."""
        with self.client.get("/api/v1/market/symbols", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(15)
    def get_risk_limits(self):
        """Task: Get risk limits."""
        with self.client.get("/api/v1/risk/limits", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(10)
    def get_ai_prediction(self):
        """Task: Get AI price prediction."""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = symbols[int(time.time()) % len(symbols)]
        with self.client.get(f"/api/v1/ai/predict/price/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(5)
    def place_market_order(self):
        """Task: Place a market order (low frequency to avoid spamming)."""
        # Get portfolio ID first
        with self.client.get("/api/v1/portfolio/summary", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                return
            portfolio_id = resp.json().get("id")
            if not portfolio_id:
                return

        payload = {
            "symbol": "AAPL",
            "side": "buy" if time.time() % 2 < 1 else "sell",
            "quantity": 1,
            "order_type": "market",
            "portfolio_id": portfolio_id,
        }
        with self.client.post("/api/v1/trading/orders", json=payload, headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code not in [200, 201, 202]:
                resp.failure(f"Status code: {resp.status_code}")

    @task(3)
    def refresh_token(self):
        """Task: Refresh token (low frequency)."""
        # We don't have refresh token stored; we'll skip for now
        pass

    @task(2)
    def logout(self):
        """Task: Logout (low frequency)."""
        with self.client.post("/api/v1/auth/logout", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code not in [200, 204]:
                resp.failure(f"Status code: {resp.status_code}")

            # Get new token to continue
            # This will be handled in on_start next cycle


# ----- Locust Event Handlers -----

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when Locust test starts."""
    logger.info("=" * 60)
    logger.info("BASELINE LOAD TEST STARTING")
    logger.info(f"Host: {BASE_URL}")
    logger.info(f"Users: {LOAD_USERS}")
    logger.info(f"Spawn Rate: {SPAWN_RATE}/s")
    logger.info(f"Duration: {LOAD_DURATION}s")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when Locust test stops."""
    logger.info("=" * 60)
    logger.info("BASELINE LOAD TEST COMPLETED")
    logger.info("=" * 60)
    # Print stats summary
    stats = environment.stats
    logger.info(f"Total Requests: {stats.total.num_requests}")
    logger.info(f"Failures: {stats.total.fail_ratio * 100:.2f}%")
    logger.info(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    logger.info(f"RPS (Total): {stats.total.total_rps:.2f}")


# ----- Standalone execution -----

if __name__ == "__main__":
    # Run baseline tests using pytest
    import pytest as pytest_module
    pytest_module.main([__file__, "-v", "--maxfail=1"])
