"""
tests/load/test_load_endurance.py

NEXUS AI Trading System - Endurance/Stability Load Tests

This module tests the system's ability to handle sustained load over extended periods,
detecting memory leaks, performance degradation, and resource exhaustion.

It measures:
- Response time trends over time (first hour vs. last hour)
- Error rate stability
- Throughput consistency
- Resource utilization (if monitoring is available)

The endurance test is designed to run for hours (configurable) with a moderate
user load to simulate real-world usage patterns.

Usage:
    pytest tests/load/test_load_endurance.py -v
    locust -f tests/load/test_load_endurance.py --host=http://localhost:8000

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import logging
import pytest
import statistics
import concurrent.futures
import threading
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque

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
ENDURANCE_DURATION = int(os.getenv("ENDURANCE_DURATION", "3600"))  # seconds (1 hour by default)
ENDURANCE_USERS = int(os.getenv("ENDURANCE_USERS", "30"))
SPAWN_RATE = int(os.getenv("ENDURANCE_SPAWN_RATE", "2"))
SAMPLE_INTERVAL = int(os.getenv("ENDURANCE_SAMPLE_INTERVAL", "60"))  # seconds between metric samples

# Performance thresholds for endurance
ENDURANCE_THRESHOLDS = {
    "avg_response_time": 1.0,                    # 1 second average
    "p95_response_time": 2.0,                    # 2 seconds
    "error_rate": 0.02,                          # 2% max error rate
    "throughput_min": 5,                         # 5 requests per second minimum
    "degradation_threshold": 0.20,               # 20% max degradation over time
    "memory_leak_threshold": 0.10,               # 10% max memory increase per hour
}

# Critical endpoints for endurance testing
ENDPOINTS = [
    {"name": "portfolio_summary", "method": "GET", "path": "/portfolio/summary", "weight": 20},
    {"name": "market_quote", "method": "GET", "path": "/market/quote/AAPL", "weight": 25},
    {"name": "users_me", "method": "GET", "path": "/users/me", "weight": 15},
    {"name": "positions", "method": "GET", "path": "/portfolio/positions", "weight": 20},
    {"name": "market_symbols", "method": "GET", "path": "/market/symbols", "weight": 10},
    {"name": "risk_limits", "method": "GET", "path": "/risk/limits", "weight": 5},
    {"name": "ai_prediction", "method": "GET", "path": "/ai/predict/price/AAPL", "weight": 5},
]


# ----- Helper Functions -----

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
    email = os.getenv("TEST_USER_EMAIL", "test@nexusquantum.com")
    password = os.getenv("TEST_USER_PASSWORD", "Test@123")
    token = get_auth_token(session, email, password)
    if token:
        return {"email": email, "password": password, "token": token}
    logger.error("Failed to authenticate load test user")
    return None


# ----- Metric Collector (thread-safe) -----

class EnduranceMetrics:
    """Collect and analyze metrics over time."""

    def __init__(self, window_size: int = 1000):
        self.lock = threading.Lock()
        self.response_times = {}  # endpoint -> list of (timestamp, time)
        self.error_counts = {}    # endpoint -> int
        self.total_requests = {}  # endpoint -> int
        self.start_time = None
        self.window_size = window_size
        # For rolling metrics
        self.rolling_windows = defaultdict(lambda: deque(maxlen=window_size))

    def record(self, endpoint: str, elapsed: float, success: bool):
        """Record a single request metric."""
        with self.lock:
            timestamp = time.time()
            if self.start_time is None:
                self.start_time = timestamp
            if endpoint not in self.response_times:
                self.response_times[endpoint] = []
                self.error_counts[endpoint] = 0
                self.total_requests[endpoint] = 0
            self.response_times[endpoint].append((timestamp, elapsed))
            self.rolling_windows[endpoint].append((timestamp, elapsed, success))
            self.total_requests[endpoint] += 1
            if not success:
                self.error_counts[endpoint] += 1

    def get_stats(self, endpoint: str = None) -> Dict[str, Any]:
        """Get statistics for an endpoint or overall."""
        with self.lock:
            if endpoint:
                return self._compute_stats(endpoint)
            else:
                # Aggregate all endpoints
                all_times = []
                all_errors = 0
                all_total = 0
                for ep in self.response_times:
                    stats = self._compute_stats(ep)
                    all_times.extend([t for _, t in stats["times"]])
                    all_errors += stats["errors"]
                    all_total += stats["total"]
                return {
                    "endpoint": "overall",
                    "avg_response": statistics.mean(all_times) if all_times else 0,
                    "p95_response": sorted(all_times)[int(len(all_times) * 0.95)] if all_times else 0,
                    "error_rate": all_errors / all_total if all_total > 0 else 0,
                    "total_requests": all_total,
                    "errors": all_errors,
                    "times": all_times,
                }

    def _compute_stats(self, endpoint: str) -> Dict[str, Any]:
        """Compute stats for a single endpoint."""
        times = self.response_times.get(endpoint, [])
        errors = self.error_counts.get(endpoint, 0)
        total = self.total_requests.get(endpoint, 0)
        if not times:
            return {"endpoint": endpoint, "avg_response": 0, "p95_response": 0, "error_rate": 0, "total": 0, "errors": 0, "times": []}
        response_values = [t for _, t in times]
        avg = statistics.mean(response_values)
        p95 = sorted(response_values)[int(len(response_values) * 0.95)]
        error_rate = errors / total if total > 0 else 0
        return {
            "endpoint": endpoint,
            "avg_response": avg,
            "p95_response": p95,
            "error_rate": error_rate,
            "total": total,
            "errors": errors,
            "times": times,
        }

    def get_trend(self, endpoint: str, num_segments: int = 10) -> Dict[str, Any]:
        """Return metrics segmented over time to detect degradation."""
        with self.lock:
            times = self.response_times.get(endpoint, [])
            if not times:
                return {}
            # Sort by timestamp
            times.sort(key=lambda x: x[0])
            total = len(times)
            segment_size = max(1, total // num_segments)
            segments = []
            for i in range(0, total, segment_size):
                segment_times = [t for _, t in times[i:i+segment_size]]
                if segment_times:
                    avg = statistics.mean(segment_times)
                    p95 = sorted(segment_times)[int(len(segment_times) * 0.95)]
                    start_ts = times[i][0]
                    end_ts = times[min(i+segment_size-1, total-1)][0]
                    segments.append({
                        "start_time": start_ts,
                        "end_time": end_ts,
                        "avg_response": avg,
                        "p95_response": p95,
                        "count": len(segment_times),
                    })
            return {
                "endpoint": endpoint,
                "segments": segments,
                "total": total,
            }

    def get_rolling_stats(self, endpoint: str, window_seconds: int = 300) -> Dict[str, Any]:
        """Get stats for the last N seconds."""
        with self.lock:
            cutoff = time.time() - window_seconds
            window_data = [item for item in self.rolling_windows[endpoint] if item[0] >= cutoff]
            if not window_data:
                return {}
            times = [item[1] for item in window_data]
            successes = [item[2] for item in window_data]
            avg = statistics.mean(times) if times else 0
            p95 = sorted(times)[int(len(times) * 0.95)] if times else 0
            total = len(window_data)
            errors = total - sum(successes)
            error_rate = errors / total if total > 0 else 0
            return {
                "endpoint": endpoint,
                "window_seconds": window_seconds,
                "avg_response": avg,
                "p95_response": p95,
                "error_rate": error_rate,
                "total": total,
                "errors": errors,
            }


# Global metrics collector
metrics = EnduranceMetrics()


# ----- Pytest-based Endurance Test -----

@pytest.mark.load
@pytest.mark.endurance
class TestEndurance:
    """Endurance/stability tests using pytest (run for a limited time)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session and user."""
        self.session = create_session_with_retries()
        self.user = setup_test_user(self.session)
        assert self.user is not None, "Failed to set up test user"
        self.auth_headers = {"Authorization": f"Bearer {self.user['token']}"}
        self.results = defaultdict(list)
        # Clear global metrics
        global metrics
        metrics = EnduranceMetrics()
        yield
        self.session.close()

    def _make_request(self, endpoint: dict) -> Tuple[str, float, bool]:
        """Make a single request and return metric."""
        name = endpoint["name"]
        method = endpoint["method"]
        path = endpoint["path"]
        url = f"{API_URL}{path}"
        start = time.time()
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=self.auth_headers, timeout=10)
            elif method.upper() == "POST":
                response = self.session.post(url, headers=self.auth_headers, timeout=10)
            else:
                response = self.session.request(method, url, headers=self.auth_headers, timeout=10)
            elapsed = time.time() - start
            success = response.status_code < 400
            return (name, elapsed, success)
        except Exception:
            return (name, time.time() - start, False)

    def test_endurance_run(self):
        """
        Run endurance test for a configured duration.
        This will run for ENDURANCE_DURATION seconds (default 1 hour).
        For CI, we might run a shorter version (e.g., 5 minutes).
        """
        duration = ENDURANCE_DURATION
        # If environment is CI, run shorter
        if os.getenv("CI", "false").lower() == "true":
            duration = min(duration, 300)  # 5 minutes in CI
            logger.info("Running in CI mode, reducing endurance duration to 300s")

        logger.info(f"Starting endurance test for {duration} seconds")
        start_time = time.time()
        end_time = start_time + duration
        request_count = 0
        error_count = 0
        last_report_time = start_time

        # Weighted endpoint selection
        weights = [ep["weight"] for ep in ENDPOINTS]
        total_weight = sum(weights)
        endpoints_with_weight = list(zip(ENDPOINTS, weights))

        while time.time() < end_time:
            # Select endpoint based on weight
            r = random.random() * total_weight
            cumulative = 0
            selected = ENDPOINTS[-1]
            for ep, w in endpoints_with_weight:
                cumulative += w
                if r <= cumulative:
                    selected = ep
                    break

            name, elapsed, success = self._make_request(selected)
            global metrics
            metrics.record(name, elapsed, success)

            request_count += 1
            if not success:
                error_count += 1

            # Report every SAMPLE_INTERVAL seconds
            now = time.time()
            if now - last_report_time >= SAMPLE_INTERVAL:
                self._report_metrics(now - start_time)
                last_report_time = now

            # Add a small pause to simulate think time
            time.sleep(random.uniform(0.1, 0.5))

        # Final report
        logger.info("=" * 60)
        logger.info("ENDURANCE TEST COMPLETED")
        logger.info(f"Duration: {time.time() - start_time:.2f}s")
        logger.info(f"Total requests: {request_count}")
        logger.info(f"Error rate: {error_count/request_count:.2%}")
        logger.info("=" * 60)

        # Analyze degradation
        self._analyze_degradation()

        # Assert thresholds
        final_stats = metrics.get_stats()
        assert final_stats["avg_response"] < ENDURANCE_THRESHOLDS["avg_response_time"], \
            f"Average response time {final_stats['avg_response']:.3f}s > threshold {ENDURANCE_THRESHOLDS['avg_response_time']}s"
        assert final_stats["p95_response"] < ENDURANCE_THRESHOLDS["p95_response_time"], \
            f"p95 response time {final_stats['p95_response']:.3f}s > threshold {ENDURANCE_THRESHOLDS['p95_response_time']}s"
        assert final_stats["error_rate"] < ENDURANCE_THRESHOLDS["error_rate"], \
            f"Error rate {final_stats['error_rate']:.2%} > threshold {ENDURANCE_THRESHOLDS['error_rate']:.2%}"

    def _report_metrics(self, elapsed: float):
        """Log current metrics."""
        stats = metrics.get_stats()
        logger.info(f"[{elapsed:.0f}s] "
                    f"Avg: {stats['avg_response']*1000:.1f}ms, "
                    f"p95: {stats['p95_response']*1000:.1f}ms, "
                    f"Errors: {stats['error_rate']:.2%}, "
                    f"Total: {stats['total_requests']}")

    def _analyze_degradation(self):
        """Analyze performance degradation over time."""
        # Get trend for the most used endpoint (e.g., portfolio_summary)
        endpoint_name = "portfolio_summary"
        trend = metrics.get_trend(endpoint_name, num_segments=10)
        if not trend or len(trend["segments"]) < 3:
            logger.warning("Insufficient data for degradation analysis")
            return

        segments = trend["segments"]
        first_avg = segments[0]["avg_response"]
        last_avg = segments[-1]["avg_response"]
        degradation = (last_avg - first_avg) / first_avg if first_avg > 0 else 0

        logger.info(f"Degradation analysis for {endpoint_name}:")
        logger.info(f"  First segment avg: {first_avg*1000:.1f}ms")
        logger.info(f"  Last segment avg: {last_avg*1000:.1f}ms")
        logger.info(f"  Degradation: {degradation*100:.2f}%")

        # Assert degradation is within threshold
        assert degradation < ENDURANCE_THRESHOLDS["degradation_threshold"], \
            f"Degradation {degradation*100:.2f}% > threshold {ENDURANCE_THRESHOLDS['degradation_threshold']*100:.2f}%"

        # Also check error rate per segment
        # We don't have per-segment error rates, so we'll skip.

    def test_memory_leak_indicators(self):
        """Check for indicators of memory leaks (e.g., increasing response times)."""
        # This is a proxy: if response times consistently increase, it's a sign.
        # We'll run a shorter test (5 minutes) to detect increasing trend.
        duration = 300  # 5 minutes
        logger.info(f"Running memory leak indicator test for {duration}s")
        start_time = time.time()
        end_time = start_time + duration
        sample_times = []
        sample_avgs = []

        while time.time() < end_time:
            ep = ENDPOINTS[0]  # use first endpoint
            name, elapsed, success = self._make_request(ep)
            global metrics
            metrics.record(name, elapsed, success)
            sample_times.append(time.time() - start_time)
            sample_avgs.append(elapsed)
            time.sleep(1)

        # Check if average response time increases by more than 50% from first half to second half
        if len(sample_avgs) > 20:
            first_half = sample_avgs[:len(sample_avgs)//2]
            second_half = sample_avgs[len(sample_avgs)//2:]
            avg_first = statistics.mean(first_half)
            avg_second = statistics.mean(second_half)
            increase = (avg_second - avg_first) / avg_first if avg_first > 0 else 0
            logger.info(f"Memory leak indicator: avg first half={avg_first*1000:.1f}ms, avg second half={avg_second*1000:.1f}ms, increase={increase*100:.2f}%")
            # Fail if increase > 30%
            assert increase < 0.30, f"Response time increased by {increase*100:.2f}% (>30%)"


# ----- Locust User Definition for Endurance Testing -----

class EnduranceTestUser(HttpUser):
    """
    Locust user that runs an endurance test with periodic checks.
    """
    host = BASE_URL
    wait_time = between(1, 3)
    token = None
    start_time = None
    last_report_time = None

    def on_start(self):
        """Authenticate and set up."""
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
        self.start_time = time.time()
        self.last_report_time = self.start_time

    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(25)
    def portfolio_summary(self):
        with self.client.get("/api/v1/portfolio/summary", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            global metrics
            metrics.record("portfolio_summary", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            self._check_report()

    @task(20)
    def market_quote(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            metrics.record("market_quote", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            self._check_report()

    @task(15)
    def get_user(self):
        with self.client.get("/api/v1/users/me", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            metrics.record("users_me", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            self._check_report()

    @task(15)
    def get_positions(self):
        with self.client.get("/api/v1/portfolio/positions", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            metrics.record("positions", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            self._check_report()

    @task(10)
    def market_symbols(self):
        with self.client.get("/api/v1/market/symbols", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            metrics.record("market_symbols", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            self._check_report()

    @task(10)
    def ai_prediction(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/ai/predict/price/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            metrics.record("ai_prediction", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            self._check_report()

    @task(5)
    def risk_limits(self):
        with self.client.get("/api/v1/risk/limits", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            metrics.record("risk_limits", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            self._check_report()

    def _check_report(self):
        """Periodically report metrics."""
        now = time.time()
        if now - self.last_report_time >= SAMPLE_INTERVAL:
            stats = metrics.get_stats()
            logger.info(f"[{now - self.start_time:.0f}s] "
                        f"Avg: {stats['avg_response']*1000:.1f}ms, "
                        f"p95: {stats['p95_response']*1000:.1f}ms, "
                        f"Errors: {stats['error_rate']:.2%}")
            self.last_report_time = now


# ----- Locust Event Handlers -----

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("ENDURANCE LOAD TEST STARTING")
    logger.info(f"Host: {BASE_URL}")
    logger.info(f"Users: {ENDURANCE_USERS}")
    logger.info(f"Spawn Rate: {SPAWN_RATE}/s")
    logger.info(f"Duration: {ENDURANCE_DURATION}s")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("ENDURANCE LOAD TEST COMPLETED")
    logger.info("=" * 60)
    stats = environment.stats
    logger.info(f"Total Requests: {stats.total.num_requests}")
    logger.info(f"Failures: {stats.total.fail_ratio * 100:.2f}%")
    logger.info(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    logger.info(f"RPS (Total): {stats.total.total_rps:.2f}")

    # Analyze degradation
    global metrics
    stats_overall = metrics.get_stats()
    logger.info(f"Overall Avg: {stats_overall['avg_response']*1000:.1f}ms")
    logger.info(f"Overall p95: {stats_overall['p95_response']*1000:.1f}ms")

    # Check trend for a key endpoint
    endpoint_name = "portfolio_summary"
    trend = metrics.get_trend(endpoint_name, num_segments=10)
    if trend and len(trend["segments"]) >= 3:
        first = trend["segments"][0]["avg_response"]
        last = trend["segments"][-1]["avg_response"]
        degradation = (last - first) / first if first > 0 else 0
        logger.info(f"Degradation for {endpoint_name}: {degradation*100:.2f}%")
        if degradation > ENDURANCE_THRESHOLDS["degradation_threshold"]:
            logger.warning(f"⚠️ Degradation exceeds threshold: {degradation*100:.2f}% > {ENDURANCE_THRESHOLDS['degradation_threshold']*100:.2f}%")


# ----- Standalone execution -----

if __name__ == "__main__":
    import pytest as pytest_module
    pytest_module.main([__file__, "-v", "--maxfail=1"])
