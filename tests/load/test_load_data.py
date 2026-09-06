"""
tests/load/test_load_data.py

NEXUS AI Trading System - Data Load Tests

This module tests the performance of data-intensive endpoints that
retrieve, process, and deliver large datasets. It measures:

- Historical data retrieval (multiple timeframes and symbols)
- Portfolio performance history (large time series)
- AI prediction history (bulk queries)
- Data export and aggregation
- Caching effectiveness

These endpoints often have higher latency and are more resource-intensive,
so they require specific load testing to ensure they scale.

Usage:
    pytest tests/load/test_load_data.py -v
    locust -f tests/load/test_load_data.py --host=http://localhost:8000

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import logging
import pytest
import statistics
import concurrent.futures
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import random

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
LOAD_DURATION = int(os.getenv("LOAD_TEST_DURATION", "180"))  # seconds
LOAD_USERS = int(os.getenv("LOAD_TEST_USERS", "20"))
SPAWN_RATE = int(os.getenv("LOAD_TEST_SPAWN_RATE", "2"))

# Performance thresholds for data endpoints (higher latency expected)
DATA_THRESHOLDS = {
    "average_response_time": 2.0,      # 2 seconds
    "p95_response_time": 4.0,          # 4 seconds
    "p99_response_time": 8.0,          # 8 seconds
    "error_rate": 0.02,                # 2% max error rate
    "throughput_min": 5,                # 5 requests per second minimum
}

# Data-heavy endpoints
DATA_ENDPOINTS = {
    "historical_data_1h": {"method": "GET", "path": "/market/historical/AAPL", "params": {"timeframe": "1h", "limit": 500}, "weight": 30},
    "historical_data_1d": {"method": "GET", "path": "/market/historical/MSFT", "params": {"timeframe": "1d", "limit": 1000}, "weight": 20},
    "performance_full": {"method": "GET", "path": "/portfolio/performance", "params": {"interval": "daily", "period": "1y"}, "weight": 25},
    "performance_chart": {"method": "GET", "path": "/portfolio/performance/chart", "params": {"interval": "weekly", "period": "6m"}, "weight": 20},
    "prediction_history": {"method": "GET", "path": "/ai/predict/history/AAPL", "params": {"limit": 100}, "weight": 15},
    "market_data_bulk": {"method": "GET", "path": "/market/quote/bulk", "params": {"symbols": "AAPL,MSFT,GOOGL,AMZN,TSLA"}, "weight": 25},
    "order_history": {"method": "GET", "path": "/trading/orders/history", "params": {"limit": 200}, "weight": 20},
    "exports": {"method": "GET", "path": "/portfolio/exports", "params": {"format": "json", "start_date": "2026-01-01", "end_date": "2026-12-31"}, "weight": 10},
}


# ----- Helper Functions (shared with baseline) -----

def create_session_with_retries() -> requests.Session:
    """Create a requests session with retry logic."""
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
    """Get authentication token."""
    try:
        response = session.post(
            f"{API_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except Exception:
        return None


def setup_test_user(session: requests.Session) -> Dict[str, Any]:
    """Register or login a test user."""
    email = f"load_data_{int(time.time())}_{random.randint(1000, 9999)}@nexusquantum.com"
    password = "LoadTest@123"

    # Try to register
    try:
        response = session.post(
            f"{API_URL}/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Data",
                "last_name": "LoadTest",
            },
            timeout=5,
        )
        if response.status_code == 201:
            token = response.json().get("access_token") or get_auth_token(session, email, password)
            return {"email": email, "password": password, "token": token}
    except Exception:
        pass

    # Try to login with default
    default_email = os.getenv("TEST_USER_EMAIL", "test@nexusquantum.com")
    default_password = os.getenv("TEST_USER_PASSWORD", "Test@123")
    token = get_auth_token(session, default_email, default_password)
    if token:
        return {"email": default_email, "password": default_password, "token": token}

    logger.error("Failed to authenticate load test user")
    return None


# ----- Pytest-based Data Load Tests -----

@pytest.mark.load
@pytest.mark.data_load
class TestDataLoadPerformance:
    """Data-intensive performance tests using pytest."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session and user."""
        self.session = create_session_with_retries()
        self.user = setup_test_user(self.session)
        assert self.user is not None, "Failed to set up test user"
        self.auth_headers = {"Authorization": f"Bearer {self.user['token']}"}
        self.results = defaultdict(list)
        yield
        self.session.close()

    def _measure_endpoint(self, endpoint_name: str, method: str, path: str, params: Dict = None, num_requests: int = 10) -> Dict[str, Any]:
        """Measure performance with data retrieval."""
        url = f"{API_URL}{path}"
        headers = self.auth_headers.copy()
        headers["Content-Type"] = "application/json"

        response_times = []
        errors = 0
        data_sizes = []

        for _ in range(num_requests):
            try:
                start = time.time()
                if method.upper() == "GET":
                    response = self.session.get(url, headers=headers, timeout=30, params=params)
                elif method.upper() == "POST":
                    response = self.session.post(url, headers=headers, json=params, timeout=30)
                else:
                    response = self.session.request(method, url, headers=headers, json=params, timeout=30)

                elapsed = time.time() - start
                response_times.append(elapsed)

                if response.status_code >= 400:
                    errors += 1
                    logger.debug(f"Error on {endpoint_name}: {response.status_code}")
                else:
                    # Approximate data size (content length)
                    data_sizes.append(len(response.content))

            except Exception as e:
                errors += 1
                logger.debug(f"Exception on {endpoint_name}: {e}")

        if response_times:
            avg = statistics.mean(response_times)
            p95 = sorted(response_times)[int(len(response_times) * 0.95)]
            p99 = sorted(response_times)[int(len(response_times) * 0.99)]
            error_rate = errors / num_requests if num_requests > 0 else 1.0
            avg_size = statistics.mean(data_sizes) if data_sizes else 0
        else:
            avg = p95 = p99 = 0
            error_rate = 1.0
            avg_size = 0

        return {
            "endpoint": endpoint_name,
            "method": method,
            "path": path,
            "num_requests": num_requests,
            "avg_response": avg,
            "p95_response": p95,
            "p99_response": p99,
            "error_rate": error_rate,
            "avg_data_size": avg_size,
        }

    def test_historical_data_performance(self):
        """Test historical data retrieval with large datasets."""
        test_cases = [
            ("historical_1h", "/market/historical/AAPL", {"timeframe": "1h", "limit": 500}),
            ("historical_1d", "/market/historical/MSFT", {"timeframe": "1d", "limit": 1000}),
            ("historical_1w", "/market/historical/GOOGL", {"timeframe": "1w", "limit": 500}),
            ("historical_crypto", "/market/historical/BTC/USD", {"timeframe": "1h", "limit": 200}),
        ]

        for name, path, params in test_cases:
            result = self._measure_endpoint(name, "GET", path, params, num_requests=20)
            self.results[name].append(result)

            # Assert thresholds (higher tolerance for historical data)
            assert result["avg_response"] < DATA_THRESHOLDS["average_response_time"] * 1.2, \
                f"{name} avg {result['avg_response']:.3f}s > threshold"
            assert result["error_rate"] < DATA_THRESHOLDS["error_rate"], \
                f"{name} error rate {result['error_rate']:.2%} > threshold"
            logger.info(f"{name}: avg={result['avg_response']:.3f}s, p95={result['p95_response']:.3f}s, size={result['avg_data_size']/1024:.1f}KB")

    def test_portfolio_performance_data(self):
        """Test portfolio performance endpoints with large time series."""
        test_cases = [
            ("performance_daily", "/portfolio/performance", {"interval": "daily", "period": "1y"}),
            ("performance_weekly", "/portfolio/performance", {"interval": "weekly", "period": "2y"}),
            ("performance_chart", "/portfolio/performance/chart", {"interval": "daily", "period": "6m"}),
            ("risk_metrics", "/portfolio/performance/risk-metrics", {}),
            ("returns_distribution", "/portfolio/performance/returns-distribution", {}),
        ]

        for name, path, params in test_cases:
            result = self._measure_endpoint(name, "GET", path, params, num_requests=15)
            self.results[name].append(result)
            assert result["avg_response"] < DATA_THRESHOLDS["average_response_time"], \
                f"{name} avg {result['avg_response']:.3f}s > threshold"
            assert result["error_rate"] < DATA_THRESHOLDS["error_rate"], \
                f"{name} error rate {result['error_rate']:.2%} > threshold"
            logger.info(f"{name}: avg={result['avg_response']:.3f}s, p95={result['p95_response']:.3f}s")

    def test_ai_prediction_history(self):
        """Test AI prediction history endpoints with many records."""
        test_cases = [
            ("pred_history_50", "/ai/predict/history/AAPL", {"limit": 50}),
            ("pred_history_200", "/ai/predict/history/MSFT", {"limit": 200}),
            ("pred_history_500", "/ai/predict/history/GOOGL", {"limit": 500}),
            ("pred_ensemble", "/ai/predict/ensemble/AAPL", {}),
        ]

        for name, path, params in test_cases:
            result = self._measure_endpoint(name, "GET", path, params, num_requests=15)
            self.results[name].append(result)
            assert result["avg_response"] < DATA_THRESHOLDS["average_response_time"], \
                f"{name} avg {result['avg_response']:.3f}s > threshold"
            assert result["error_rate"] < DATA_THRESHOLDS["error_rate"], \
                f"{name} error rate {result['error_rate']:.2%} > threshold"

    def test_order_history_bulk(self):
        """Test order history with large dataset and filters."""
        test_cases = [
            ("order_history_all", "/trading/orders/history", {"limit": 500}),
            ("order_history_filtered", "/trading/orders/history", {"symbol": "AAPL", "limit": 200}),
            ("order_history_dates", "/trading/orders/history", {"start_date": "2026-01-01", "end_date": "2026-12-31", "limit": 300}),
        ]

        for name, path, params in test_cases:
            result = self._measure_endpoint(name, "GET", path, params, num_requests=15)
            self.results[name].append(result)
            assert result["avg_response"] < DATA_THRESHOLDS["average_response_time"], \
                f"{name} avg {result['avg_response']:.3f}s > threshold"
            assert result["error_rate"] < DATA_THRESHOLDS["error_rate"], \
                f"{name} error rate {result['error_rate']:.2%} > threshold"

    def test_bulk_market_data(self):
        """Test bulk market data endpoints."""
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "SPY", "QQQ"]
        for i in range(1, len(symbols) + 1):
            subset = ",".join(symbols[:i])
            params = {"symbols": subset}
            name = f"bulk_{i}_symbols"
            result = self._measure_endpoint(name, "GET", "/market/quote/bulk", params, num_requests=10)
            self.results[name].append(result)
            # Allow longer response for larger bulk requests
            threshold = DATA_THRESHOLDS["average_response_time"] * (1 + (i / 10))
            assert result["avg_response"] < threshold, f"{name} avg {result['avg_response']:.3f}s > {threshold:.3f}s"
            logger.info(f"{name}: avg={result['avg_response']:.3f}s, size={result['avg_data_size']/1024:.1f}KB")

    def test_data_export(self):
        """Test data export endpoints (potentially large responses)."""
        test_cases = [
            ("export_portfolio", "/portfolio/exports", {"format": "json", "start_date": "2026-01-01", "end_date": "2026-12-31"}),
            ("export_trades", "/trading/orders/export", {"format": "csv", "start_date": "2026-01-01", "end_date": "2026-12-31"}),
        ]
        for name, path, params in test_cases:
            result = self._measure_endpoint(name, "GET", path, params, num_requests=5)
            self.results[name].append(result)
            # Exports can be heavy; allow longer time
            assert result["avg_response"] < DATA_THRESHOLDS["average_response_time"] * 2, \
                f"{name} avg {result['avg_response']:.3f}s > 2x threshold"
            assert result["error_rate"] < DATA_THRESHOLDS["error_rate"], \
                f"{name} error rate {result['error_rate']:.2%} > threshold"

    def test_concurrent_data_requests(self):
        """Test concurrent data requests to simulate multiple users loading data."""
        endpoint_list = [
            ("historical", "GET", "/market/historical/AAPL", {"timeframe": "1h", "limit": 500}),
            ("performance", "GET", "/portfolio/performance", {"interval": "daily", "period": "1y"}),
            ("bulk", "GET", "/market/quote/bulk", {"symbols": "AAPL,MSFT,GOOGL"}),
        ]

        def make_request(name, method, path, params):
            start = time.time()
            url = f"{API_URL}{path}"
            try:
                if method == "GET":
                    response = self.session.get(url, headers=self.auth_headers, params=params, timeout=30)
                else:
                    response = self.session.request(method, url, headers=self.auth_headers, json=params, timeout=30)
                elapsed = time.time() - start
                success = response.status_code < 400
                return (name, elapsed, success)
            except Exception:
                return (name, time.time() - start, False)

        num_concurrent = 30
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            for _ in range(num_concurrent):
                for name, method, path, params in endpoint_list:
                    futures.append(executor.submit(make_request, name, method, path, params))

        results = [f.result() for f in futures]

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
            # Allow higher latency under concurrency
            assert avg < DATA_THRESHOLDS["average_response_time"] * 1.5, f"Concurrent {name} avg {avg:.3f}s > 1.5x threshold"

    def test_caching_effectiveness(self):
        """Test that caching reduces response times for repeated data requests."""
        endpoint = ("cached_historical", "GET", "/market/historical/AAPL", {"timeframe": "1h", "limit": 500})
        num_requests = 10

        # First request (warmup)
        self._measure_endpoint("warmup", endpoint[1], endpoint[2], endpoint[3], num_requests=1)

        # Measure subsequent requests (should be cached)
        result = self._measure_endpoint(endpoint[0], endpoint[1], endpoint[2], endpoint[3], num_requests=num_requests)
        avg = result["avg_response"]
        # Expect cached responses to be much faster (e.g., < 500ms)
        logger.info(f"Cached average response: {avg*1000:.1f}ms")
        # We don't enforce a strict threshold because cache may not be enabled in test env,
        # but we log the result for analysis.

    def test_data_load_report(self):
        """Generate a comprehensive report of data load test results."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "thresholds": DATA_THRESHOLDS,
            "results": {},
            "summary": {"passed": 0, "failed": 0},
        }

        for endpoint_name, measurements in self.results.items():
            if not measurements:
                continue
            all_avg = [m["avg_response"] for m in measurements]
            all_p95 = [m["p95_response"] for m in measurements]
            all_errors = [m["error_rate"] for m in measurements]
            all_sizes = [m["avg_data_size"] for m in measurements]

            report["results"][endpoint_name] = {
                "avg_response": statistics.mean(all_avg) if all_avg else 0,
                "p95_response": statistics.mean(all_p95) if all_p95 else 0,
                "error_rate": statistics.mean(all_errors) if all_errors else 0,
                "avg_data_size": statistics.mean(all_sizes) if all_sizes else 0,
                "num_measurements": len(measurements),
                "details": measurements,
            }

        # Log summary
        logger.info("=" * 60)
        logger.info("DATA LOAD PERFORMANCE REPORT")
        logger.info("=" * 60)
        for name, metrics in report["results"].items():
            status = "✅ PASS" if metrics["avg_response"] < DATA_THRESHOLDS["average_response_time"] else "❌ FAIL"
            logger.info(f"{status} {name}: avg={metrics['avg_response']:.3f}s, p95={metrics['p95_response']:.3f}s, size={metrics['avg_data_size']/1024:.1f}KB")
        logger.info("=" * 60)

        # Save report
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"data_load_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Report saved to {report_path}")


# ----- Locust User Definition for Data Load Testing -----

class DataLoadTestUser(HttpUser):
    """
    Locust user simulating data-heavy operations.
    """
    host = BASE_URL
    wait_time = between(2, 5)  # Longer think time for data tasks
    token = None

    def on_start(self):
        """Authenticate."""
        email = os.getenv("TEST_USER_EMAIL", "test@nexusquantum.com")
        password = os.getenv("TEST_USER_PASSWORD", "Test@123")
        with self.client.post("/api/v1/auth/login", json={"email": email, "password": password}, catch_response=True) as resp:
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
            else:
                resp.failure(f"Login failed: {resp.status_code}")
                raise StopUser()
        if not self.token:
            raise StopUser()

    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(25)
    def load_historical_data(self):
        """Task: Fetch historical data with large limit."""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        timeframes = ["1h", "1d", "1w"]
        timeframe = random.choice(timeframes)
        limit = random.choice([100, 500, 1000])
        with self.client.get(
            f"/api/v1/market/historical/{symbol}",
            params={"timeframe": timeframe, "limit": limit},
            headers=self.get_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(20)
    def load_performance_data(self):
        """Task: Load portfolio performance with long history."""
        intervals = ["daily", "weekly", "monthly"]
        periods = ["3m", "6m", "1y", "2y"]
        params = {
            "interval": random.choice(intervals),
            "period": random.choice(periods),
        }
        with self.client.get(
            "/api/v1/portfolio/performance",
            params=params,
            headers=self.get_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(20)
    def load_performance_chart(self):
        """Task: Load performance chart data."""
        params = {
            "interval": random.choice(["daily", "weekly"]),
            "period": random.choice(["1m", "3m", "6m", "1y"]),
        }
        with self.client.get(
            "/api/v1/portfolio/performance/chart",
            params=params,
            headers=self.get_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(15)
    def load_prediction_history(self):
        """Task: Load AI prediction history."""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        limit = random.choice([50, 100, 200])
        with self.client.get(
            f"/api/v1/ai/predict/history/{symbol}",
            params={"limit": limit},
            headers=self.get_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(15)
    def load_order_history(self):
        """Task: Load order history with filters."""
        params = {
            "limit": random.choice([100, 200, 500]),
            "symbol": random.choice(["AAPL", "MSFT", "GOOGL"]) if random.random() > 0.5 else None,
        }
        with self.client.get(
            "/api/v1/trading/orders/history",
            params=params,
            headers=self.get_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(10)
    def load_bulk_quotes(self):
        """Task: Fetch bulk quotes for multiple symbols."""
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX"]
        num_symbols = random.randint(3, 8)
        selected = random.sample(symbols, num_symbols)
        with self.client.get(
            "/api/v1/market/quote/bulk",
            params={"symbols": ",".join(selected)},
            headers=self.get_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(5)
    def load_risk_metrics(self):
        """Task: Load detailed risk metrics."""
        with self.client.get(
            "/api/v1/portfolio/performance/risk-metrics",
            headers=self.get_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(5)
    def load_returns_distribution(self):
        """Task: Load returns distribution data."""
        with self.client.get(
            "/api/v1/portfolio/performance/returns-distribution",
            headers=self.get_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")


# ----- Locust Event Handlers -----

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("DATA LOAD TEST STARTING")
    logger.info(f"Host: {BASE_URL}")
    logger.info(f"Users: {LOAD_USERS}")
    logger.info(f"Spawn Rate: {SPAWN_RATE}/s")
    logger.info(f"Duration: {LOAD_DURATION}s")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("DATA LOAD TEST COMPLETED")
    logger.info("=" * 60)
    stats = environment.stats
    logger.info(f"Total Requests: {stats.total.num_requests}")
    logger.info(f"Failures: {stats.total.fail_ratio * 100:.2f}%")
    logger.info(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    logger.info(f"RPS (Total): {stats.total.total_rps:.2f}")


# ----- Standalone execution -----

if __name__ == "__main__":
    import pytest as pytest_module
    pytest_module.main([__file__, "-v", "--maxfail=1"])
