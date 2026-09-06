"""
tests/load/test_load_ramp.py

NEXUS AI Trading System - Ramp Load Tests

This module tests system behavior under gradually increasing and decreasing load.
It simulates realistic traffic patterns such as:

- Morning ramp-up as users log in throughout the day
- Peak load during market hours
- Evening ramp-down as activity decreases

Tests measure:
- Performance degradation during load increase
- Recovery during load decrease
- Peak performance thresholds
- Resource exhaustion under ramp-up

The ramp test runs for a configurable duration with a specified ramp-up time,
peak load duration, and ramp-down time.

Usage:
    pytest tests/load/test_load_ramp.py -v
    locust -f tests/load/test_load_ramp.py --host=http://localhost:8000

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import logging
import pytest
import statistics
import threading
import math
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
RAMP_DURATION = int(os.getenv("RAMP_DURATION", "300"))  # seconds total
RAMP_UP_TIME = int(os.getenv("RAMP_UP_TIME", "60"))      # seconds to reach peak
PEAK_TIME = int(os.getenv("RAMP_PEAK_TIME", "120"))       # seconds at peak
RAMP_DOWN_TIME = int(os.getenv("RAMP_DOWN_TIME", "60"))   # seconds to ramp down
MIN_USERS = int(os.getenv("RAMP_MIN_USERS", "1"))
MAX_USERS = int(os.getenv("RAMP_MAX_USERS", "50"))
SPAWN_RATE = int(os.getenv("RAMP_SPAWN_RATE", "2"))

# Performance thresholds for ramp test
RAMP_THRESHOLDS = {
    "avg_response": 1.5,           # seconds
    "p95_response": 3.0,           # seconds
    "error_rate": 0.03,            # 3% max error rate
    "max_degradation": 1.5,        # ratio: peak avg / low avg <= 2.5x allowed
}

# Endpoints for ramp test
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
    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
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
    email = f"ramp_test_{int(time.time())}_{random.randint(1000, 9999)}@nexusquantum.com"
    password = "LoadTest@123"
    try:
        response = session.post(
            f"{API_URL}/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Ramp",
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
    logger.error("Failed to authenticate ramp load user")
    return None


# ----- Metric Collector -----

class RampMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.response_times = {}  # endpoint -> list of (timestamp, time)
        self.error_counts = {}
        self.total_requests = {}
        self.start_time = None
        self.samples = []  # (timestamp, user_count, avg_response, error_rate)

    def record(self, endpoint: str, elapsed: float, success: bool):
        with self.lock:
            ts = time.time()
            if self.start_time is None:
                self.start_time = ts
            if endpoint not in self.response_times:
                self.response_times[endpoint] = []
                self.error_counts[endpoint] = 0
                self.total_requests[endpoint] = 0
            self.response_times[endpoint].append((ts, elapsed))
            self.total_requests[endpoint] += 1
            if not success:
                self.error_counts[endpoint] += 1

    def get_stats(self, endpoint: str = None) -> Dict[str, Any]:
        with self.lock:
            if endpoint:
                return self._compute_stats(endpoint)
            else:
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
                }

    def _compute_stats(self, endpoint: str) -> Dict[str, Any]:
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

    def get_samples(self, num_segments: int = 20) -> List[Dict[str, Any]]:
        """Return performance samples over time."""
        with self.lock:
            overall_times = []
            for ep in self.response_times:
                overall_times.extend([(ts, t) for ts, t in self.response_times[ep]])
            if not overall_times:
                return []
            overall_times.sort(key=lambda x: x[0])
            total = len(overall_times)
            segment_size = max(1, total // num_segments)
            samples = []
            for i in range(0, total, segment_size):
                segment = overall_times[i:i+segment_size]
                if segment:
                    ts_avg = sum(ts for ts, _ in segment) / len(segment)
                    times = [t for _, t in segment]
                    avg = statistics.mean(times)
                    p95 = sorted(times)[int(len(times) * 0.95)]
                    # Estimate user count based on time (simplified: we don't have real user count)
                    # We'll derive from elapsed time since start
                    elapsed = ts_avg - self.start_time if self.start_time else 0
                    samples.append({
                        "timestamp": ts_avg,
                        "elapsed": elapsed,
                        "avg_response": avg,
                        "p95_response": p95,
                        "count": len(segment),
                    })
            return samples


ramp_metrics = RampMetrics()


# ----- Pytest-based Ramp Test -----

@pytest.mark.load
@pytest.mark.ramp
class TestRampLoad:
    """Ramp load tests with increasing and decreasing user load."""

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

    def test_ramp_load(self):
        """
        Simulate ramp-up, peak, and ramp-down load.
        This test runs for RAMP_DURATION seconds with controlled user count.
        For pytest, we'll simulate varying request rates rather than actual users.
        We'll adjust request frequency based on the phase.
        """
        total_duration = RAMP_DURATION
        if os.getenv("CI", "false").lower() == "true":
            total_duration = min(total_duration, 120)  # 2 minutes in CI
            logger.info("CI mode: reducing ramp test duration to 120s")

        ramp_up = min(RAMP_UP_TIME, total_duration // 3)
        peak = min(PEAK_TIME, total_duration // 3)
        ramp_down = min(RAMP_DOWN_TIME, total_duration // 3)
        # Adjust to fit total duration
        if ramp_up + peak + ramp_down < total_duration:
            # Add extra to peak
            peak += total_duration - (ramp_up + peak + ramp_down)

        logger.info(f"Ramp test: {ramp_up}s up, {peak}s peak, {ramp_down}s down (total {total_duration}s)")

        start_time = time.time()
        end_time = start_time + total_duration
        last_report = start_time
        request_count = 0
        error_count = 0

        # Weighted endpoint selection
        weights = [ep["weight"] for ep in ENDPOINTS]
        total_weight = sum(weights)
        weighted_eps = list(zip(ENDPOINTS, weights))

        while time.time() < end_time:
            elapsed = time.time() - start_time

            # Determine phase and target request rate (requests per second)
            if elapsed < ramp_up:
                # Ramp up: linear increase from MIN_USERS to MAX_USERS
                fraction = elapsed / ramp_up
                target_rate = MIN_USERS + (MAX_USERS - MIN_USERS) * fraction
                target_rate = max(MIN_USERS, target_rate)
            elif elapsed < ramp_up + peak:
                # Peak load: MAX_USERS
                target_rate = MAX_USERS
            else:
                # Ramp down: linear decrease from MAX_USERS to MIN_USERS
                fraction = (elapsed - ramp_up - peak) / ramp_down
                target_rate = MAX_USERS - (MAX_USERS - MIN_USERS) * fraction
                target_rate = max(MIN_USERS, target_rate)

            # Convert users to requests per second (each user might do 1 req per 1-3 sec)
            # We'll use target_rate as approximate req/s.
            # But we want to scale requests; we'll just make one request per iteration.
            # To adjust rate, we'll vary sleep time.
            # Sleep time = 1 / target_rate if target_rate > 0 else 1
            if target_rate > 0:
                sleep_time = 1.0 / target_rate
                # Clamp sleep time between 0.05 and 2 seconds
                sleep_time = min(max(sleep_time, 0.05), 2.0)
            else:
                sleep_time = 2.0

            # Select endpoint
            r = random.random() * total_weight
            cumulative = 0
            selected = ENDPOINTS[-1]
            for ep, w in weighted_eps:
                cumulative += w
                if r <= cumulative:
                    selected = ep
                    break

            name, elapsed_req, success = self._make_request(selected)
            ramp_metrics.record(name, elapsed_req, success)
            request_count += 1
            if not success:
                error_count += 1

            # Report every SAMPLE_INTERVAL (e.g., 30 sec)
            now = time.time()
            if now - last_report >= 30:
                stats = ramp_metrics.get_stats()
                logger.info(f"[{elapsed:.0f}s] Users: ~{target_rate:.1f}, "
                            f"Avg: {stats['avg_response']*1000:.1f}ms, "
                            f"p95: {stats['p95_response']*1000:.1f}ms, "
                            f"Errors: {stats['error_rate']:.2%}")
                last_report = now

            time.sleep(sleep_time)

        # Final report
        logger.info("=" * 60)
        logger.info("RAMP LOAD TEST COMPLETED")
        logger.info(f"Total requests: {request_count}")
        logger.info(f"Error rate: {error_count/request_count:.2%}")
        logger.info("=" * 60)

        # Analyze degradation across load levels
        samples = ramp_metrics.get_samples(num_segments=10)
        if len(samples) >= 3:
            # Split into low, mid, high load based on estimated user count
            # Use elapsed time to approximate (early vs late)
            # We'll look at the first third (ramp-up), middle (peak), last third (ramp-down)
            total = len(samples)
            low_load = samples[:total//3]
            high_load = samples[total//3:2*total//3]
            end_load = samples[2*total//3:]

            avg_low = statistics.mean([s["avg_response"] for s in low_load]) if low_load else 0
            avg_high = statistics.mean([s["avg_response"] for s in high_load]) if high_load else 0
            avg_end = statistics.mean([s["avg_response"] for s in end_load]) if end_load else 0

            logger.info(f"Low load avg: {avg_low*1000:.1f}ms")
            logger.info(f"High load avg: {avg_high*1000:.1f}ms")
            logger.info(f"End load avg: {avg_end*1000:.1f}ms")

            # Check degradation: high load should not be more than 2.5x low load
            if avg_low > 0:
                degradation_high = avg_high / avg_low
                logger.info(f"Degradation factor (peak vs low): {degradation_high:.2f}x")
                assert degradation_high < RAMP_THRESHOLDS["max_degradation"], \
                    f"Degradation {degradation_high:.2f}x > threshold {RAMP_THRESHOLDS['max_degradation']}x"

            # Recovery: end load should be close to low load (within 1.5x)
            if avg_low > 0:
                recovery_factor = avg_end / avg_low
                logger.info(f"Recovery factor (end vs low): {recovery_factor:.2f}x")
                assert recovery_factor < 1.5, f"Recovery poor: {recovery_factor:.2f}x > 1.5x"

        # Overall thresholds
        overall = ramp_metrics.get_stats()
        assert overall["avg_response"] < RAMP_THRESHOLDS["avg_response"], \
            f"Overall avg {overall['avg_response']:.3f}s > threshold"
        assert overall["p95_response"] < RAMP_THRESHOLDS["p95_response"], \
            f"Overall p95 {overall['p95_response']:.3f}s > threshold"
        assert overall["error_rate"] < RAMP_THRESHOLDS["error_rate"], \
            f"Overall error rate {overall['error_rate']:.2%} > threshold"

        # Save report
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "ramp_up": ramp_up,
            "peak": peak,
            "ramp_down": ramp_down,
            "min_users": MIN_USERS,
            "max_users": MAX_USERS,
            "results": {
                "overall": overall,
                "samples": samples,
            },
            "thresholds": RAMP_THRESHOLDS,
        }
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"ramp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Report saved to {report_path}")


# ----- Locust Ramp User Definition -----

class RampLoadUser(HttpUser):
    """
    Locust user that adapts to the ramp load shape.
    We'll use a custom load shape in the locustfile, but we can also adjust
    wait_time dynamically based on elapsed time.
    """
    host = BASE_URL
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
            ramp_metrics.record("portfolio_summary", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(25)
    def market_quote(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            ramp_metrics.record("market_quote", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(20)
    def positions(self):
        with self.client.get("/api/v1/portfolio/positions", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            ramp_metrics.record("positions", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(15)
    def market_symbols(self):
        with self.client.get("/api/v1/market/symbols", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            ramp_metrics.record("market_symbols", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")

    @task(10)
    def ai_prediction(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/ai/predict/price/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            ramp_metrics.record("ai_prediction", elapsed, resp.status_code < 400)
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")


# ----- Locust custom load shape -----

class RampLoadShape:
    """
    Custom load shape for Locust that implements ramp-up, peak, ramp-down.
    """
    min_users = MIN_USERS
    max_users = MAX_USERS
    ramp_up_time = RAMP_UP_TIME
    peak_time = PEAK_TIME
    ramp_down_time = RAMP_DOWN_TIME
    total_time = RAMP_DURATION

    def tick(self):
        """
        Returns a tuple (user_count, spawn_rate) or None to stop.
        Called every second by Locust.
        """
        run_time = self.get_run_time()  # seconds since test start

        if run_time < self.ramp_up_time:
            # Ramp up
            fraction = run_time / self.ramp_up_time
            user_count = self.min_users + (self.max_users - self.min_users) * fraction
            spawn_rate = max(1, (user_count - self.min_users) / self.ramp_up_time * self.ramp_up_time)
            return (int(user_count), int(spawn_rate) + 1)

        elif run_time < self.ramp_up_time + self.peak_time:
            # Peak
            return (self.max_users, 1)

        elif run_time < self.ramp_up_time + self.peak_time + self.ramp_down_time:
            # Ramp down
            elapsed_down = run_time - (self.ramp_up_time + self.peak_time)
            fraction = elapsed_down / self.ramp_down_time
            user_count = self.max_users - (self.max_users - self.min_users) * fraction
            spawn_rate = max(1, (self.max_users - user_count) / self.ramp_down_time * self.ramp_down_time)
            return (int(user_count), int(spawn_rate) + 1)

        else:
            # End test
            return None


# ----- Locust Event Handlers -----

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("RAMP LOAD TEST STARTING (Locust)")
    logger.info(f"Host: {BASE_URL}")
    logger.info(f"Min Users: {MIN_USERS}, Max Users: {MAX_USERS}")
    logger.info(f"Ramp Up: {RAMP_UP_TIME}s, Peak: {PEAK_TIME}s, Ramp Down: {RAMP_DOWN_TIME}s")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("RAMP LOAD TEST COMPLETED (Locust)")
    logger.info("=" * 60)
    stats = environment.stats
    logger.info(f"Total Requests: {stats.total.num_requests}")
    logger.info(f"Failures: {stats.total.fail_ratio * 100:.2f}%")
    logger.info(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    logger.info(f"RPS (Total): {stats.total.total_rps:.2f}")

    overall = ramp_metrics.get_stats()
    logger.info(f"Overall Avg: {overall['avg_response']*1000:.1f}ms")
    logger.info(f"Overall p95: {overall['p95_response']*1000:.1f}ms")
    logger.info(f"Overall Error Rate: {overall['error_rate']:.2%}")


# ----- Locust wrapper -----

# To use the custom load shape with Locust, you would set:
# locust -f tests/load/test_load_ramp.py --host=http://localhost:8000 --headless -u 1 -r 1 --run-time 300
# But since we have a custom shape, the user count and spawn rate are ignored, so we can just:
# locust -f tests/load/test_load_ramp.py --host=http://localhost:8000 --headless

# We also need a way to tell Locust to use the custom shape.
# We can do this by setting a class attribute on the environment.

if __name__ == "__main__":
    # For pytest execution
    import pytest as pytest_module
    pytest_module.main([__file__, "-v", "--maxfail=1"])
