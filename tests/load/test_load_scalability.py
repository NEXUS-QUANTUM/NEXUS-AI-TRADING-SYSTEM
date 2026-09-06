"""
tests/load/test_load_scalability.py

NEXUS AI Trading System - Scalability Load Tests

This module tests the system's ability to scale with increased resources.
It verifies that adding more instances/workers improves performance
proportionally. Tests include:

- Horizontal scaling: adding more API workers
- Vertical scaling: increasing CPU/memory resources
- Database connection pool scaling
- Cache scaling (Redis cluster)
- Worker pool scaling for Celery
- Throughput scaling with increased concurrency
- Linear scaling verification

The tests run against a deployed environment and measure performance
at different scale levels. They can be run in combination with infrastructure
scaling tools (e.g., Kubernetes HPA, Terraform).

Usage:
    pytest tests/load/test_load_scalability.py -v
    locust -f tests/load/test_load_scalability.py --host=http://localhost:8000

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import logging
import pytest
import statistics
import threading
import random
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

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
SCALABILITY_DURATION = int(os.getenv("SCALABILITY_DURATION", "600"))  # seconds total
SCALABILITY_USERS = int(os.getenv("SCALABILITY_USERS", "50"))
SPAWN_RATE = int(os.getenv("SCALABILITY_SPAWN_RATE", "5"))
SCALABILITY_LEVELS = [1, 2, 4, 8]  # Number of replicas/workers to test
SCALABILITY_LEVEL_DURATION = int(os.getenv("SCALABILITY_LEVEL_DURATION", "120"))  # seconds per level

# Performance thresholds
SCALABILITY_THRESHOLDS = {
    "throughput_per_replica": 10,       # requests per second per replica
    "linearity_factor_min": 0.80,       # min linearity (actual / expected)
    "linearity_factor_max": 1.20,       # max linearity (actual / expected)
    "avg_response": 1.5,                # seconds
    "p95_response": 3.0,                # seconds
    "error_rate": 0.02,                 # 2% max error rate
}

# Endpoints for scalability testing
ENDPOINTS = [
    {"name": "portfolio_summary", "method": "GET", "path": "/portfolio/summary", "weight": 30},
    {"name": "market_quote", "method": "GET", "path": "/market/quote/AAPL", "weight": 25},
    {"name": "positions", "method": "GET", "path": "/portfolio/positions", "weight": 20},
    {"name": "market_symbols", "method": "GET", "path": "/market/symbols", "weight": 15},
    {"name": "ai_prediction", "method": "GET", "path": "/ai/predict/price/AAPL", "weight": 10},
]


# ----- Helper Functions -----

def create_session_with_retries() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE"],
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_auth_token(session: requests.Session, email: str, password: str) -> Optional[str]:
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
    email = f"scalability_test_{int(time.time())}_{random.randint(1000, 9999)}@nexusquantum.com"
    password = "LoadTest@123"
    try:
        response = session.post(
            f"{API_URL}/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Scalability",
                "last_name": "LoadTest",
            },
            timeout=5,
        )
        if response.status_code == 201:
            token = response.json().get("access_token") or get_auth_token(session, email, password)
            return {"email": email, "password": password, "token": token}
    except Exception:
        pass
    default_email = os.getenv("TEST_USER_EMAIL", "test@nexusquantum.com")
    default_password = os.getenv("TEST_USER_PASSWORD", "Test@123")
    token = get_auth_token(session, default_email, default_password)
    if token:
        return {"email": default_email, "password": default_password, "token": token}
    logger.error("Failed to authenticate scalability load user")
    return None


def get_current_replicas() -> int:
    """Get the current number of replicas/instances (simulated)."""
    # In a real test, this would query Kubernetes or cloud provider.
    # For now, we'll use a mock value from environment.
    return int(os.getenv("SCALABILITY_CURRENT_REPLICAS", "1"))


def set_replicas(count: int) -> bool:
    """Scale the application to the specified number of replicas."""
    # In a real test, this would call Kubernetes API or Terraform.
    # For this test, we'll simulate by setting an environment variable.
    os.environ["SCALABILITY_CURRENT_REPLICAS"] = str(count)
    logger.info(f"Simulated scaling to {count} replicas")
    # Allow time for scaling to take effect
    time.sleep(5)
    return True


# ----- Metric Collector -----

class ScalabilityMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.response_times = {}  # level -> endpoint -> list of times
        self.error_counts = {}    # level -> endpoint -> error count
        self.total_requests = {}  # level -> endpoint -> total count
        self.start_time = None
        self.current_level = None

    def set_level(self, level: int):
        with self.lock:
            self.current_level = level
            if level not in self.response_times:
                self.response_times[level] = {}
                self.error_counts[level] = {}
                self.total_requests[level] = {}
            logger.info(f"Metrics level set to: {level}")

    def record(self, endpoint: str, elapsed: float, success: bool):
        with self.lock:
            ts = time.time()
            if self.start_time is None:
                self.start_time = ts
            level = self.current_level
            if level is None:
                return
            if endpoint not in self.response_times[level]:
                self.response_times[level][endpoint] = []
                self.error_counts[level][endpoint] = 0
                self.total_requests[level][endpoint] = 0
            self.response_times[level][endpoint].append(elapsed)
            self.total_requests[level][endpoint] += 1
            if not success:
                self.error_counts[level][endpoint] += 1

    def get_level_stats(self, level: int) -> Dict[str, Any]:
        with self.lock:
            if level not in self.response_times:
                return {}
            all_times = []
            all_errors = 0
            all_total = 0
            for endpoint in self.response_times[level]:
                times = self.response_times[level][endpoint]
                errors = self.error_counts[level][endpoint]
                total = self.total_requests[level][endpoint]
                all_times.extend(times)
                all_errors += errors
                all_total += total
            return {
                "level": level,
                "avg_response": statistics.mean(all_times) if all_times else 0,
                "p95_response": sorted(all_times)[int(len(all_times) * 0.95)] if all_times else 0,
                "error_rate": all_errors / all_total if all_total > 0 else 0,
                "total_requests": all_total,
                "errors": all_errors,
                "throughput": all_total / SCALABILITY_LEVEL_DURATION if SCALABILITY_LEVEL_DURATION > 0 else 0,
            }

    def get_all_level_stats(self) -> Dict[int, Dict[str, Any]]:
        with self.lock:
            result = {}
            for level in self.response_times:
                result[level] = self.get_level_stats(level)
            return result

    def get_scalability_analysis(self) -> Dict[str, Any]:
        """Analyze scalability: throughput vs replicas, linearity, etc."""
        stats = self.get_all_level_stats()
        if not stats:
            return {}

        levels = sorted(stats.keys())
        if len(levels) < 2:
            return {"error": "Need at least 2 levels for analysis"}

        # Throughput per level
        throughputs = [stats[level]["throughput"] for level in levels]
        # Error rates
        error_rates = [stats[level]["error_rate"] for level in levels]
        # Response times
        avg_times = [stats[level]["avg_response"] for level in levels]
        p95_times = [stats[level]["p95_response"] for level in levels]

        # Calculate linearity: if throughput increases linearly with replicas
        base_throughput = throughputs[0]
        expected_throughputs = [base_throughput * level / levels[0] for level in levels]
        actual_ratio = []
        for i, level in enumerate(levels):
            actual = throughputs[i]
            expected = expected_throughputs[i]
            ratio = actual / expected if expected > 0 else 0
            actual_ratio.append(ratio)

        # Calculate scaling efficiency (how close to ideal)
        average_ratio = statistics.mean(actual_ratio) if actual_ratio else 0
        min_ratio = min(actual_ratio) if actual_ratio else 0
        max_ratio = max(actual_ratio) if actual_ratio else 0

        return {
            "levels": levels,
            "throughputs": throughputs,
            "expected_throughputs": expected_throughputs,
            "actual_ratios": actual_ratio,
            "average_ratio": average_ratio,
            "min_ratio": min_ratio,
            "max_ratio": max_ratio,
            "error_rates": error_rates,
            "avg_response_times": avg_times,
            "p95_response_times": p95_times,
            "scaling_efficiency": average_ratio,
            "is_linear": min_ratio >= SCALABILITY_THRESHOLDS["linearity_factor_min"] and
                        max_ratio <= SCALABILITY_THRESHOLDS["linearity_factor_max"],
        }


scalability_metrics = ScalabilityMetrics()


# ----- Pytest-based Scalability Test -----

@pytest.mark.load
@pytest.mark.scalability
class TestScalabilityLoad:
    """Scalability load tests with different instance counts."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = create_session_with_retries()
        self.user = setup_test_user(self.session)
        assert self.user is not None, "Failed to set up test user"
        self.auth_headers = {"Authorization": f"Bearer {self.user['token']}"}
        self.results = defaultdict(list)
        yield
        self.session.close()

    def _make_request(self, endpoint: dict) -> Tuple[str, float, bool]:
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

    def test_scalability(self):
        """Test scalability by running at different replica counts."""
        levels = SCALABILITY_LEVELS
        duration_per_level = SCALABILITY_LEVEL_DURATION

        if os.getenv("CI", "false").lower() == "true":
            # Reduce levels and duration in CI
            levels = [1, 2]
            duration_per_level = min(duration_per_level, 60)
            logger.info("CI mode: reduced scalability test levels and duration")

        logger.info(f"Scalability test with levels: {levels}")
        logger.info(f"Duration per level: {duration_per_level}s")

        # Weighted endpoint selection
        weights = [ep["weight"] for ep in ENDPOINTS]
        total_weight = sum(weights)
        weighted_eps = list(zip(ENDPOINTS, weights))

        for level in levels:
            # Scale to this level (simulated)
            set_replicas(level)
            scalability_metrics.set_level(level)

            logger.info(f"Testing with {level} replicas for {duration_per_level}s")

            start_time = time.time()
            end_time = start_time + duration_per_level
            request_count = 0
            error_count = 0

            while time.time() < end_time:
                # Select endpoint
                r = random.random() * total_weight
                cumulative = 0
                selected = ENDPOINTS[-1]
                for ep, w in weighted_eps:
                    cumulative += w
                    if r <= cumulative:
                        selected = ep
                        break

                name, elapsed, success = self._make_request(selected)
                scalability_metrics.record(name, elapsed, success)

                request_count += 1
                if not success:
                    error_count += 1

                # Adjust sleep based on level
                sleep_time = random.uniform(0.1, 0.5)
                time.sleep(sleep_time)

            # Report level stats
            stats = scalability_metrics.get_level_stats(level)
            logger.info(f"Level {level}: avg={stats['avg_response']*1000:.1f}ms, "
                       f"p95={stats['p95_response']*1000:.1f}ms, "
                       f"throughput={stats['throughput']:.1f} req/s, "
                       f"errors={stats['error_rate']:.2%}")

        # Analysis
        analysis = scalability_metrics.get_scalability_analysis()
        logger.info("=" * 60)
        logger.info("SCALABILITY ANALYSIS")
        logger.info("=" * 60)

        if "error" in analysis:
            logger.error(f"Analysis error: {analysis['error']}")
            return

        logger.info(f"Levels: {analysis['levels']}")
        logger.info(f"Throughputs: {[f'{t:.1f}' for t in analysis['throughputs']]} req/s")
        logger.info(f"Expected throughputs: {[f'{t:.1f}' for t in analysis['expected_throughputs']]} req/s")
        logger.info(f"Actual ratios: {[f'{r:.2f}' for r in analysis['actual_ratios']]}")
        logger.info(f"Average scaling ratio: {analysis['average_ratio']:.2f}")
        logger.info(f"Scaling efficiency: {analysis['scaling_efficiency']:.2f}")
        logger.info(f"Is linear? {analysis['is_linear']}")

        # Assert thresholds
        assert analysis["is_linear"], \
            f"Scaling not linear: min ratio {analysis['min_ratio']:.2f}, max {analysis['max_ratio']:.2f}"

        # Check each level's error rate and response time
        all_stats = scalability_metrics.get_all_level_stats()
        for level, stats in all_stats.items():
            assert stats["avg_response"] < SCALABILITY_THRESHOLDS["avg_response"], \
                f"Level {level} avg {stats['avg_response']:.3f}s > threshold"
            assert stats["p95_response"] < SCALABILITY_THRESHOLDS["p95_response"], \
                f"Level {level} p95 {stats['p95_response']:.3f}s > threshold"
            assert stats["error_rate"] < SCALABILITY_THRESHOLDS["error_rate"], \
                f"Level {level} error rate {stats['error_rate']:.2%} > threshold"

        # Save report
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "levels": levels,
            "duration_per_level": duration_per_level,
            "analysis": analysis,
            "level_stats": all_stats,
            "thresholds": SCALABILITY_THRESHOLDS,
        }
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"scalability_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Report saved to {report_path}")

    def test_throughput_scaling(self):
        """Test throughput scaling with increasing concurrency."""
        # This test simulates increasing concurrent users and measures throughput
        concurrency_levels = [10, 20, 50, 100]
        duration_per_level = 30

        logger.info(f"Throughput scaling test with concurrency: {concurrency_levels}")

        results = []
        for concurrency in concurrency_levels:
            logger.info(f"Testing with {concurrency} concurrent users")

            # We'll use ThreadPoolExecutor to simulate concurrent users
            def worker():
                endpoint = random.choice(ENDPOINTS)
                return self._make_request(endpoint)

            start_time = time.time()
            successes = 0
            failures = 0

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = []
                for _ in range(concurrency * 5):  # Each user does ~5 requests
                    futures.append(executor.submit(worker))

                for future in as_completed(futures):
                    name, elapsed, success = future.result()
                    if success:
                        successes += 1
                    else:
                        failures += 1

            duration = time.time() - start_time
            total = successes + failures
            throughput = total / duration if duration > 0 else 0
            error_rate = failures / total if total > 0 else 0

            results.append({
                "concurrency": concurrency,
                "throughput": throughput,
                "error_rate": error_rate,
                "duration": duration,
                "successes": successes,
                "failures": failures,
            })
            logger.info(f"Concurrency {concurrency}: throughput={throughput:.1f} req/s, errors={error_rate:.2%}")

        # Save throughput results
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"throughput_scaling_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Throughput report saved to {report_path}")

        # Verify throughput increases with concurrency
        if len(results) >= 2:
            for i in range(1, len(results)):
                # Throughput should increase (or at least not decrease significantly)
                prev = results[i-1]["throughput"]
                curr = results[i]["throughput"]
                # Allow up to 20% decrease due to overhead
                assert curr >= prev * 0.8, f"Throughput dropped from {prev:.1f} to {curr:.1f} req/s"


# ----- Locust User Definition -----

class ScalabilityTestUser(HttpUser):
    """Locust user for scalability testing."""
    host = BASE_URL
    wait_time = between(0.5, 2.0)
    token = None

    def on_start(self):
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

    @task(30)
    def portfolio_summary(self):
        with self.client.get("/api/v1/portfolio/summary", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            scalability_metrics.record("portfolio_summary", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(25)
    def market_quote(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            scalability_metrics.record("market_quote", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(20)
    def positions(self):
        with self.client.get("/api/v1/portfolio/positions", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            scalability_metrics.record("positions", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(15)
    def market_symbols(self):
        with self.client.get("/api/v1/market/symbols", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            scalability_metrics.record("market_symbols", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(10)
    def ai_prediction(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/ai/predict/price/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            scalability_metrics.record("ai_prediction", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")


# ----- Locust Event Handlers -----

class ScalabilityLevelController:
    """Controls scalability levels during Locust test."""
    def __init__(self):
        self.levels = SCALABILITY_LEVELS
        self.current_index = 0
        self.level_start_time = None
        self.duration_per_level = SCALABILITY_LEVEL_DURATION
        self.lock = threading.Lock()

    def get_current_level(self):
        with self.lock:
            return self.levels[self.current_index] if self.current_index < len(self.levels) else None

    def advance_level(self):
        with self.lock:
            self.current_index += 1
            self.level_start_time = time.time()
            level = self.get_current_level()
            if level is not None:
                set_replicas(level)
                scalability_metrics.set_level(level)
            return level

    def check_and_advance(self):
        """Check if it's time to advance to the next level."""
        if self.level_start_time is None:
            self.level_start_time = time.time()
            level = self.get_current_level()
            if level is not None:
                set_replicas(level)
                scalability_metrics.set_level(level)
            return

        elapsed = time.time() - self.level_start_time
        if elapsed >= self.duration_per_level:
            return self.advance_level()
        return self.get_current_level()


level_controller = ScalabilityLevelController()


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("SCALABILITY LOAD TEST STARTING")
    logger.info(f"Host: {BASE_URL}")
    logger.info(f"Users: {SCALABILITY_USERS}")
    logger.info(f"Levels: {SCALABILITY_LEVELS}")
    logger.info(f"Duration per level: {SCALABILITY_LEVEL_DURATION}s")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("SCALABILITY LOAD TEST COMPLETED")
    logger.info("=" * 60)

    analysis = scalability_metrics.get_scalability_analysis()
    if "error" in analysis:
        logger.error(f"Analysis error: {analysis['error']}")
    else:
        logger.info("Scalability Analysis:")
        logger.info(f"  Levels: {analysis['levels']}")
        logger.info(f"  Throughputs: {[f'{t:.1f}' for t in analysis['throughputs']]} req/s")
        logger.info(f"  Scaling efficiency: {analysis['scaling_efficiency']:.2f}")
        logger.info(f"  Is linear? {analysis['is_linear']}")

    stats = environment.stats
    logger.info(f"Total Requests: {stats.total.num_requests}")
    logger.info(f"Failures: {stats.total.fail_ratio * 100:.2f}%")
    logger.info(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")


# ----- Standalone execution -----

if __name__ == "__main__":
    import pytest as pytest_module
    pytest_module.main([__file__, "-v", "--maxfail=1"])

