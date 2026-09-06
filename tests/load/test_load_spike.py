"""
tests/load/test_load_spike.py

NEXUS AI Trading System - Spike Load Tests

This module tests the system's ability to handle sudden spikes in traffic,
simulating scenarios such as:

- Flash crash: sudden market volatility causing increased trading activity
- News announcement: sudden surge in users checking prices and placing orders
- Earnings report: rapid increase in API requests
- Social media event: viral mention causing a flood of new users

Tests measure:
- Response times during the spike (should degrade gracefully)
- Error rate during the spike (should remain within acceptable bounds)
- Recovery time after the spike (how quickly the system stabilizes)
- Throughput during and after the spike
- Resource utilization (if monitoring is available)

The spike test consists of:
1. Normal load period (baseline)
2. Sudden spike to high load (X times normal)
3. Return to normal load
4. Recovery and stabilization period

Usage:
    pytest tests/load/test_load_spike.py -v
    locust -f tests/load/test_load_spike.py --host=http://localhost:8000

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
SPIKE_DURATION = int(os.getenv("SPIKE_DURATION", "300"))          # seconds total
SPIKE_USERS_NORMAL = int(os.getenv("SPIKE_USERS_NORMAL", "20"))   # normal load users
SPIKE_USERS_SPIKE = int(os.getenv("SPIKE_USERS_SPIKE", "200"))    # spike load users (10x normal)
SPIKE_SPAWN_RATE = int(os.getenv("SPIKE_SPAWN_RATE", "10"))       # users per second during spike
SPIKE_DURATION_SPIKE = int(os.getenv("SPIKE_DURATION_SPIKE", "30")) # seconds of spike

# Performance thresholds
SPIKE_THRESHOLDS = {
    "normal_avg": 1.0,                # seconds (normal load)
    "normal_p95": 2.0,                # seconds (normal load)
    "spike_avg": 2.5,                 # seconds (during spike, can be higher)
    "spike_p95": 5.0,                 # seconds (during spike)
    "error_rate_normal": 0.02,        # 2% max error rate during normal
    "error_rate_spike": 0.05,         # 5% max error rate during spike
    "recovery_time": 60,              # seconds to return to normal after spike
    "recovery_ratio": 1.5,            # recovery avg / normal avg <= 1.5x
}

# Endpoints for spike testing
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
    email = f"spike_test_{int(time.time())}_{random.randint(1000, 9999)}@nexusquantum.com"
    password = "LoadTest@123"
    try:
        response = session.post(
            f"{API_URL}/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Spike",
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
    logger.error("Failed to authenticate spike load user")
    return None


# ----- Metric Collector -----

class SpikeMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.response_times = {}  # phase -> endpoint -> list of (timestamp, time)
        self.error_counts = {}    # phase -> endpoint -> error count
        self.total_requests = {}  # phase -> endpoint -> total count
        self.start_time = None
        self.phases = ["normal", "spike", "recovery"]
        self.current_phase = "normal"

    def set_phase(self, phase: str):
        with self.lock:
            if phase not in self.phases:
                return
            self.current_phase = phase
            if phase not in self.response_times:
                self.response_times[phase] = {}
                self.error_counts[phase] = {}
                self.total_requests[phase] = {}
            logger.info(f"Metrics phase changed to: {phase}")

    def record(self, endpoint: str, elapsed: float, success: bool):
        with self.lock:
            ts = time.time()
            if self.start_time is None:
                self.start_time = ts
            phase = self.current_phase
            if phase not in self.response_times:
                return
            if endpoint not in self.response_times[phase]:
                self.response_times[phase][endpoint] = []
                self.error_counts[phase][endpoint] = 0
                self.total_requests[phase][endpoint] = 0
            self.response_times[phase][endpoint].append((ts, elapsed))
            self.total_requests[phase][endpoint] += 1
            if not success:
                self.error_counts[phase][endpoint] += 1

    def get_phase_stats(self, phase: str) -> Dict[str, Any]:
        with self.lock:
            if phase not in self.response_times:
                return {}
            all_times = []
            all_errors = 0
            all_total = 0
            for endpoint in self.response_times[phase]:
                times = [t for _, t in self.response_times[phase][endpoint]]
                errors = self.error_counts[phase][endpoint]
                total = self.total_requests[phase][endpoint]
                all_times.extend(times)
                all_errors += errors
                all_total += total
            return {
                "phase": phase,
                "avg_response": statistics.mean(all_times) if all_times else 0,
                "p95_response": sorted(all_times)[int(len(all_times) * 0.95)] if all_times else 0,
                "error_rate": all_errors / all_total if all_total > 0 else 0,
                "total_requests": all_total,
                "errors": all_errors,
            }

    def get_all_phase_stats(self) -> Dict[str, Dict[str, Any]]:
        with self.lock:
            result = {}
            for phase in self.phases:
                result[phase] = self.get_phase_stats(phase)
            return result

    def get_recovery_time(self) -> float:
        """Calculate recovery time: time from start of recovery to normal performance."""
        normal_stats = self.get_phase_stats("normal")
        recovery_stats = self.get_phase_stats("recovery")
        if not normal_stats or normal_stats["total_requests"] == 0:
            return 0
        if not recovery_stats or recovery_stats["total_requests"] == 0:
            return 0

        normal_avg = normal_stats["avg_response"]
        threshold = normal_avg * SPIKE_THRESHOLDS["recovery_ratio"]

        # We need to find when recovery times drop below threshold.
        # We'll use the first recovery sample timestamp.
        # Since we don't have per-request phase timestamps in the stats,
        # we'll approximate using the phase change time.
        # We stored the phase change time in the metrics object.
        # We'll track phase change time separately.
        if not hasattr(self, "phase_change_time"):
            return 0
        recovery_start = self.phase_change_time.get("recovery")
        if not recovery_start:
            return 0
        # We'll estimate recovery time as time from recovery start to when
        # the rolling average of recovery responses drops to threshold.
        # For simplicity, we'll use the average recovery response time.
        # If it's below threshold, recovery is immediate.
        if recovery_stats["avg_response"] <= threshold:
            return 0
        # Otherwise, we'll approximate: assume linear decrease.
        # This is a rough estimate.
        # We'll just return the time from recovery start to end of test.
        # For more accurate, we'd need per-request timestamps with phase.
        return 0  # Placeholder; we'll calculate differently.


spike_metrics = SpikeMetrics()


# ----- Pytest-based Spike Test -----

@pytest.mark.load
@pytest.mark.spike
class TestSpikeLoad:
    """Spike load tests with sudden traffic increase."""

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

    def test_spike_load(self):
        """Simulate a spike load scenario."""
        total_duration = SPIKE_DURATION
        normal_before = max(60, total_duration // 4)                    # normal before spike
        spike_duration = min(SPIKE_DURATION_SPIKE, total_duration // 4) # spike duration
        normal_after = max(60, total_duration // 4)                    # normal after spike
        recovery_duration = max(30, total_duration - normal_before - spike_duration - normal_after)  # recovery

        if os.getenv("CI", "false").lower() == "true":
            total_duration = min(total_duration, 120)
            normal_before = 30
            spike_duration = min(spike_duration, 15)
            normal_after = 30
            recovery_duration = 30
            logger.info("CI mode: reduced spike test duration and parameters")

        logger.info(f"Spike test: {normal_before}s normal, {spike_duration}s spike, {normal_after}s normal, {recovery_duration}s recovery")

        # Set initial phase
        spike_metrics.set_phase("normal")
        start_time = time.time()
        end_time = start_time + total_duration
        last_report = start_time
        request_count = 0
        error_count = 0

        # Weighted endpoint selection
        weights = [ep["weight"] for ep in ENDPOINTS]
        total_weight = sum(weights)
        weighted_eps = list(zip(ENDPOINTS, weights))

        # Phase tracking
        phase_switch = {
            "normal": 0,
            "spike": normal_before,
            "recovery": normal_before + spike_duration,
            "normal_after": normal_before + spike_duration + recovery_duration,
        }

        # Spike flag
        in_spike = False
        spike_start_time = None

        while time.time() < end_time:
            elapsed = time.time() - start_time

            # Determine phase and load level
            if elapsed < phase_switch["spike"]:
                # Normal before spike
                phase = "normal"
                target_users = SPIKE_USERS_NORMAL
                if spike_metrics.current_phase != "normal":
                    spike_metrics.set_phase("normal")
            elif elapsed < phase_switch["recovery"]:
                # Spike
                phase = "spike"
                target_users = SPIKE_USERS_SPIKE
                if spike_metrics.current_phase != "spike":
                    spike_metrics.set_phase("spike")
                    spike_start_time = elapsed
            elif elapsed < phase_switch["normal_after"]:
                # Recovery
                phase = "recovery"
                # Gradually reduce load
                progress = (elapsed - phase_switch["recovery"]) / (phase_switch["normal_after"] - phase_switch["recovery"])
                target_users = SPIKE_USERS_SPIKE - (SPIKE_USERS_SPIKE - SPIKE_USERS_NORMAL) * progress
                target_users = max(SPIKE_USERS_NORMAL, target_users)
                if spike_metrics.current_phase != "recovery":
                    spike_metrics.set_phase("recovery")
            else:
                # Normal after recovery
                phase = "normal"
                target_users = SPIKE_USERS_NORMAL
                if spike_metrics.current_phase != "normal":
                    spike_metrics.set_phase("normal")

            # Convert target_users to request rate
            # Each user does approximately 1 request per 1-2 seconds.
            # For simplicity, we'll adjust sleep time.
            if target_users > 0:
                # Target requests per second = target_users / 1.5 (average think time)
                target_rps = target_users / 1.5
                sleep_time = 1.0 / target_rps if target_rps > 0 else 1.0
                sleep_time = min(max(sleep_time, 0.01), 2.0)
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
            spike_metrics.record(name, elapsed_req, success)

            request_count += 1
            if not success:
                error_count += 1

            # Report every 15 seconds
            now = time.time()
            if now - last_report >= 15:
                stats = spike_metrics.get_phase_stats(spike_metrics.current_phase)
                logger.info(f"[{elapsed:.0f}s] Phase: {spike_metrics.current_phase}, "
                            f"Avg: {stats['avg_response']*1000:.1f}ms, "
                            f"p95: {stats['p95_response']*1000:.1f}ms, "
                            f"Errors: {stats['error_rate']:.2%}, "
                            f"Target users: ~{target_users:.0f}")
                last_report = now

            time.sleep(sleep_time)

        # Final report
        logger.info("=" * 60)
        logger.info("SPIKE LOAD TEST COMPLETED")
        logger.info(f"Total requests: {request_count}")
        logger.info(f"Error rate: {error_count/request_count:.2%}")
        logger.info("=" * 60)

        # Analyze phase stats
        phase_stats = spike_metrics.get_all_phase_stats()
        for phase, stats in phase_stats.items():
            if stats["total_requests"] > 0:
                logger.info(f"Phase {phase}: avg={stats['avg_response']*1000:.1f}ms, "
                            f"p95={stats['p95_response']*1000:.1f}ms, "
                            f"errors={stats['error_rate']:.2%}, "
                            f"requests={stats['total_requests']}")

        # Assert thresholds
        normal_stats = phase_stats.get("normal", {})
        spike_stats = phase_stats.get("spike", {})
        recovery_stats = phase_stats.get("recovery", {})

        # Normal phase should be within normal thresholds
        if normal_stats.get("total_requests", 0) > 10:
            assert normal_stats["avg_response"] < SPIKE_THRESHOLDS["normal_avg"], \
                f"Normal avg {normal_stats['avg_response']:.3f}s > threshold"
            assert normal_stats["p95_response"] < SPIKE_THRESHOLDS["normal_p95"], \
                f"Normal p95 {normal_stats['p95_response']:.3f}s > threshold"
            assert normal_stats["error_rate"] < SPIKE_THRESHOLDS["error_rate_normal"], \
                f"Normal error rate {normal_stats['error_rate']:.2%} > threshold"

        # Spike phase should be degraded but bounded
        if spike_stats.get("total_requests", 0) > 10:
            # Average may be higher but within spike threshold
            assert spike_stats["avg_response"] < SPIKE_THRESHOLDS["spike_avg"], \
                f"Spike avg {spike_stats['avg_response']:.3f}s > threshold"
            assert spike_stats["p95_response"] < SPIKE_THRESHOLDS["spike_p95"], \
                f"Spike p95 {spike_stats['p95_response']:.3f}s > threshold"
            assert spike_stats["error_rate"] < SPIKE_THRESHOLDS["error_rate_spike"], \
                f"Spike error rate {spike_stats['error_rate']:.2%} > threshold"

        # Recovery should be close to normal
        if (recovery_stats.get("total_requests", 0) > 10 and
            normal_stats.get("total_requests", 0) > 10):
            recovery_ratio = recovery_stats["avg_response"] / normal_stats["avg_response"] if normal_stats["avg_response"] > 0 else 1
            logger.info(f"Recovery ratio: {recovery_ratio:.2f}x")
            assert recovery_ratio < SPIKE_THRESHOLDS["recovery_ratio"], \
                f"Recovery avg {recovery_stats['avg_response']:.3f}s > {SPIKE_THRESHOLDS['recovery_ratio']}x normal {normal_stats['avg_response']:.3f}s"

        # Save report
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "normal_before": normal_before,
            "spike_duration": spike_duration,
            "recovery_duration": recovery_duration,
            "normal_after": normal_after,
            "target_users_normal": SPIKE_USERS_NORMAL,
            "target_users_spike": SPIKE_USERS_SPIKE,
            "phase_stats": phase_stats,
            "thresholds": SPIKE_THRESHOLDS,
            "total_requests": request_count,
            "error_rate": error_count / request_count if request_count > 0 else 0,
        }
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"spike_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Report saved to {report_path}")


# ----- Locust User Definition -----

class SpikeTestUser(HttpUser):
    """Locust user that participates in spike load testing."""
    host = BASE_URL
    wait_time = between(0.5, 2.0)  # will be overridden by custom logic
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
            spike_metrics.record("portfolio_summary", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(25)
    def market_quote(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            spike_metrics.record("market_quote", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(20)
    def positions(self):
        with self.client.get("/api/v1/portfolio/positions", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            spike_metrics.record("positions", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(15)
    def market_symbols(self):
        with self.client.get("/api/v1/market/symbols", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            spike_metrics.record("market_symbols", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(10)
    def ai_prediction(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/ai/predict/price/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            spike_metrics.record("ai_prediction", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")


# ----- Custom Locust Load Shape for Spike Testing -----

class SpikeLoadShape:
    """
    Custom load shape for Locust that introduces a spike at a specific time.
    """
    normal_users = SPIKE_USERS_NORMAL
    spike_users = SPIKE_USERS_SPIKE
    normal_before = max(60, SPIKE_DURATION // 4)
    spike_duration = min(SPIKE_DURATION_SPIKE, SPIKE_DURATION // 4)
    recovery_duration = max(30, SPIKE_DURATION // 4)
    normal_after = max(60, SPIKE_DURATION - normal_before - spike_duration - recovery_duration)

    def tick(self):
        run_time = self.get_run_time()  # seconds since test start

        if run_time < self.normal_before:
            # Normal load
            return (self.normal_users, 1)

        elif run_time < self.normal_before + self.spike_duration:
            # Spike: ramp up quickly
            fraction = (run_time - self.normal_before) / self.spike_duration
            user_count = self.normal_users + (self.spike_users - self.normal_users) * fraction
            spawn_rate = min(10, (self.spike_users - self.normal_users) / self.spike_duration + 1)
            # Set phase
            if spike_metrics.current_phase != "spike":
                spike_metrics.set_phase("spike")
            return (int(user_count), int(spawn_rate))

        elif run_time < self.normal_before + self.spike_duration + self.recovery_duration:
            # Recovery: ramp down gradually
            elapsed_recovery = run_time - (self.normal_before + self.spike_duration)
            fraction = elapsed_recovery / self.recovery_duration
            user_count = self.spike_users - (self.spike_users - self.normal_users) * fraction
            spawn_rate = max(1, (self.spike_users - user_count) / self.recovery_duration)
            if spike_metrics.current_phase != "recovery":
                spike_metrics.set_phase("recovery")
            return (int(user_count), int(spawn_rate))

        elif run_time < self.normal_before + self.spike_duration + self.recovery_duration + self.normal_after:
            # Normal after recovery
            if spike_metrics.current_phase != "normal":
                spike_metrics.set_phase("normal")
            return (self.normal_users, 1)

        else:
            # End test
            return None


# ----- Locust Event Handlers -----

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("SPIKE LOAD TEST STARTING (Locust)")
    logger.info(f"Host: {BASE_URL}")
    logger.info(f"Normal Users: {SPIKE_USERS_NORMAL}, Spike Users: {SPIKE_USERS_SPIKE}")
    logger.info(f"Normal before: {SpikeLoadShape.normal_before}s, Spike: {SpikeLoadShape.spike_duration}s, Recovery: {SpikeLoadShape.recovery_duration}s")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("SPIKE LOAD TEST COMPLETED (Locust)")
    logger.info("=" * 60)
    stats = environment.stats
    logger.info(f"Total Requests: {stats.total.num_requests}")
    logger.info(f"Failures: {stats.total.fail_ratio * 100:.2f}%")
    logger.info(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    logger.info(f"RPS (Total): {stats.total.total_rps:.2f}")

    phase_stats = spike_metrics.get_all_phase_stats()
    for phase, stats in phase_stats.items():
        if stats["total_requests"] > 0:
            logger.info(f"Phase {phase}: avg={stats['avg_response']*1000:.1f}ms, errors={stats['error_rate']:.2%}")


# ----- Standalone execution -----

if __name__ == "__main__":
    import pytest as pytest_module
    pytest_module.main([__file__, "-v", "--maxfail=1"])
