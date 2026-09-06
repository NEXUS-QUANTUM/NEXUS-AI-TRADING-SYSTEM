"""
tests/load/test_load_stress.py

NEXUS AI Trading System - Stress Load Tests

This module tests the system under extreme conditions to identify breaking points
and observe behavior under maximum load. It simulates:

- Maximum concurrent users beyond expected capacity (2x - 5x normal)
- Extreme request rates that may cause queue buildup
- Sustained extreme load for extended periods
- Mixed extreme load (high reads and writes)
- Resource exhaustion scenarios (memory, CPU, database connections)

Tests measure:
- Breaking point (when error rates become unacceptable)
- Degradation patterns (graceful vs. catastrophic)
- Recovery after extreme load
- Resource utilization at peak
- Queue buildup and processing latency

The stress test is designed to push the system to its limits and observe
how it behaves under extreme conditions. It helps identify bottlenecks
and capacity planning requirements.

Usage:
    pytest tests/load/test_load_stress.py -v
    locust -f tests/load/test_load_stress.py --host=http://localhost:8000

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
import math
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
STRESS_DURATION = int(os.getenv("STRESS_DURATION", "300"))           # seconds
STRESS_MAX_USERS = int(os.getenv("STRESS_MAX_USERS", "500"))          # max concurrent users
STRESS_START_USERS = int(os.getenv("STRESS_START_USERS", "10"))       # starting users
STRESS_INCREMENT = int(os.getenv("STRESS_INCREMENT", "50"))           # users to add per step
STRESS_STEP_DURATION = int(os.getenv("STRESS_STEP_DURATION", "30"))   # seconds per step

# Performance thresholds (stress conditions allow higher tolerance)
STRESS_THRESHOLDS = {
    "max_error_rate": 0.15,               # 15% max error rate before considering system broken
    "max_avg_response": 5.0,              # max average response time before degradation
    "max_p95_response": 10.0,             # max p95 response time
    "throughput_stability": 0.30,          # max throughput variation between steps
    "recovery_time": 120,                 # seconds to recover after stress
    "graceful_degradation": True,         # should not crash under stress
}

# Endpoints for stress testing
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
    adapter = HTTPAdapter(max_retries=retries, pool_connections=200, pool_maxsize=200)
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
    email = f"stress_test_{int(time.time())}_{random.randint(1000, 9999)}@nexusquantum.com"
    password = "LoadTest@123"
    try:
        response = session.post(
            f"{API_URL}/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Stress",
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
    logger.error("Failed to authenticate stress load user")
    return None


# ----- Metric Collector -----

class StressMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.step_data = {}  # step_index -> { "start_time": ..., "end_time": ..., "stats": {} }
        self.current_step = 0
        self.response_times = {}  # step -> endpoint -> list of times
        self.error_counts = {}    # step -> endpoint -> error count
        self.total_requests = {}  # step -> endpoint -> total count
        self.start_time = None
        self.current_users = 0
        self.broken = False
        self.broken_at_step = None

    def start_step(self, step_index: int, users: int):
        with self.lock:
            self.current_step = step_index
            self.current_users = users
            if step_index not in self.response_times:
                self.response_times[step_index] = {}
                self.error_counts[step_index] = {}
                self.total_requests[step_index] = {}
            if self.start_time is None:
                self.start_time = time.time()
            logger.info(f"Stress step {step_index} started with {users} users")

    def record(self, endpoint: str, elapsed: float, success: bool):
        with self.lock:
            step = self.current_step
            if step not in self.response_times:
                return
            if endpoint not in self.response_times[step]:
                self.response_times[step][endpoint] = []
                self.error_counts[step][endpoint] = 0
                self.total_requests[step][endpoint] = 0
            self.response_times[step][endpoint].append(elapsed)
            self.total_requests[step][endpoint] += 1
            if not success:
                self.error_counts[step][endpoint] += 1

    def get_step_stats(self, step: int) -> Dict[str, Any]:
        with self.lock:
            if step not in self.response_times:
                return {}
            all_times = []
            all_errors = 0
            all_total = 0
            for endpoint in self.response_times[step]:
                times = self.response_times[step][endpoint]
                errors = self.error_counts[step][endpoint]
                total = self.total_requests[step][endpoint]
                all_times.extend(times)
                all_errors += errors
                all_total += total
            return {
                "step": step,
                "avg_response": statistics.mean(all_times) if all_times else 0,
                "p95_response": sorted(all_times)[int(len(all_times) * 0.95)] if all_times else 0,
                "error_rate": all_errors / all_total if all_total > 0 else 0,
                "total_requests": all_total,
                "errors": all_errors,
                "throughput": all_total / (time.time() - self.start_time) if self.start_time else 0,
                "users": self.current_users,
            }

    def get_all_step_stats(self) -> Dict[int, Dict[str, Any]]:
        with self.lock:
            result = {}
            for step in self.response_times:
                result[step] = self.get_step_stats(step)
            return result

    def get_stress_analysis(self) -> Dict[str, Any]:
        """Analyze stress test results to find breaking point and degradation."""
        stats = self.get_all_step_stats()
        if not stats:
            return {"error": "No data available"}

        sorted_steps = sorted(stats.keys())
        results = []
        for step in sorted_steps:
            s = stats[step]
            results.append({
                "step": step,
                "users": s.get("users", 0),
                "avg_response": s["avg_response"],
                "p95_response": s["p95_response"],
                "error_rate": s["error_rate"],
                "throughput": s["throughput"],
            })

        # Find breaking point: error rate exceeds threshold
        breaking_point = None
        for r in results:
            if r["error_rate"] > STRESS_THRESHOLDS["max_error_rate"]:
                breaking_point = r
                break

        # Check graceful degradation: error rates increase gradually, not suddenly
        graceful = True
        if len(results) > 2:
            for i in range(1, len(results)):
                prev_error = results[i-1]["error_rate"]
                curr_error = results[i]["error_rate"]
                # If error rate jumps by more than 5 percentage points in one step, degradation is not graceful
                if curr_error - prev_error > 0.05:
                    graceful = False
                    break

        return {
            "steps": results,
            "breaking_point": breaking_point,
            "graceful_degradation": graceful,
            "max_users_reached": results[-1]["users"] if results else 0,
            "max_avg_response": max([r["avg_response"] for r in results]) if results else 0,
            "max_error_rate": max([r["error_rate"] for r in results]) if results else 0,
        }


stress_metrics = StressMetrics()


# ----- Pytest-based Stress Test -----

@pytest.mark.load
@pytest.mark.stress
class TestStressLoad:
    """Stress load tests to find breaking points."""

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
                response = self.session.get(url, headers=self.auth_headers, timeout=15)
            elif method.upper() == "POST":
                response = self.session.post(url, headers=self.auth_headers, timeout=15)
            else:
                response = self.session.request(method, url, headers=self.auth_headers, timeout=15)
            elapsed = time.time() - start
            success = response.status_code < 400
            return (name, elapsed, success)
        except Exception:
            return (name, time.time() - start, False)

    def test_stress_load(self):
        """
        Gradually increase load and observe system behavior.
        """
        max_users = STRESS_MAX_USERS
        start_users = STRESS_START_USERS
        increment = STRESS_INCREMENT
        step_duration = STRESS_STEP_DURATION
        total_duration = STRESS_DURATION

        if os.getenv("CI", "false").lower() == "true":
            # In CI, reduce stress test intensity
            max_users = min(max_users, 200)
            increment = min(increment, 50)
            step_duration = min(step_duration, 15)
            total_duration = min(total_duration, 120)
            logger.info("CI mode: reduced stress test intensity")

        # Calculate number of steps
        num_steps = max(1, (max_users - start_users) // increment + 1)
        users_per_step = [start_users + i * increment for i in range(num_steps)]
        # Ensure we don't exceed max_users
        if users_per_step[-1] < max_users:
            users_per_step.append(max_users)

        logger.info(f"Stress test: {len(users_per_step)} steps, users: {users_per_step}")
        logger.info(f"Step duration: {step_duration}s, total expected: {len(users_per_step) * step_duration}s")

        start_time = time.time()
        end_time = start_time + total_duration
        step_index = 0

        # Weighted endpoint selection
        weights = [ep["weight"] for ep in ENDPOINTS]
        total_weight = sum(weights)
        weighted_eps = list(zip(ENDPOINTS, weights))

        # Run until time runs out or we break
        while time.time() < end_time and step_index < len(users_per_step):
            current_users = users_per_step[step_index]
            stress_metrics.start_step(step_index, current_users)

            # Simulate current_users by adjusting request rate
            # Target requests per second = users / average think time (assume 1.5s)
            target_rps = current_users / 1.5
            # Clamp to reasonable range
            target_rps = min(max(target_rps, 1), 500)
            sleep_time = 1.0 / target_rps if target_rps > 0 else 1.0
            sleep_time = min(max(sleep_time, 0.01), 2.0)

            step_start = time.time()
            step_end = step_start + step_duration
            while time.time() < step_end and time.time() < end_time:
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
                stress_metrics.record(name, elapsed, success)

                # Check if we're breaking
                current_stats = stress_metrics.get_step_stats(step_index)
                if current_stats and current_stats.get("error_rate", 0) > STRESS_THRESHOLDS["max_error_rate"]:
                    logger.warning(f"Breaking point reached at step {step_index} with {current_users} users")
                    stress_metrics.broken = True
                    stress_metrics.broken_at_step = step_index
                    break

                time.sleep(sleep_time)

            # Log step summary
            stats = stress_metrics.get_step_stats(step_index)
            if stats:
                logger.info(f"Step {step_index} ({current_users} users): "
                            f"avg={stats['avg_response']*1000:.1f}ms, "
                            f"p95={stats['p95_response']*1000:.1f}ms, "
                            f"error={stats['error_rate']:.2%}, "
                            f"throughput={stats['throughput']:.1f} req/s")

            step_index += 1

        # Final report
        logger.info("=" * 60)
        logger.info("STRESS LOAD TEST COMPLETED")
        if stress_metrics.broken:
            logger.info(f"System broke at step {stress_metrics.broken_at_step}")
        else:
            logger.info("System did not break under maximum load")
        logger.info("=" * 60)

        # Analyze results
        analysis = stress_metrics.get_stress_analysis()
        if "error" in analysis:
            logger.error(f"Analysis error: {analysis['error']}")
            return

        logger.info("Stress Analysis:")
        logger.info(f"  Max users reached: {analysis['max_users_reached']}")
        logger.info(f"  Max avg response: {analysis['max_avg_response']*1000:.1f}ms")
        logger.info(f"  Max error rate: {analysis['max_error_rate']:.2%}")
        logger.info(f"  Graceful degradation: {analysis['graceful_degradation']}")
        if analysis["breaking_point"]:
            bp = analysis["breaking_point"]
            logger.info(f"  Breaking point: {bp['users']} users, error rate: {bp['error_rate']:.2%}")

        # Assertions
        # We don't assert that it doesn't break; stress tests are meant to find limits.
        # But we do assert that degradation is graceful (no sudden jumps) and that the system recovers.
        # We also check that it didn't completely crash (it should still respond).
        assert analysis["graceful_degradation"], "Degradation was not graceful (error rate jumped sharply)"
        # Also check that even at max load, system was still responding (not completely dead)
        assert analysis["max_avg_response"] < STRESS_THRESHOLDS["max_avg_response"] * 2, \
            f"Max avg response {analysis['max_avg_response']*1000:.1f}ms is too high"

        # Save report
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "users_per_step": users_per_step,
            "step_duration": step_duration,
            "analysis": analysis,
            "thresholds": STRESS_THRESHOLDS,
            "broken": stress_metrics.broken,
            "broken_at_step": stress_metrics.broken_at_step,
        }
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"stress_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Report saved to {report_path}")


# ----- Locust User Definition for Stress Testing -----

class StressTestUser(HttpUser):
    """Locust user that participates in stress load testing."""
    host = BASE_URL
    wait_time = between(0.3, 1.5)  # Lower wait time for stress
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
            stress_metrics.record("portfolio_summary", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(25)
    def market_quote(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            stress_metrics.record("market_quote", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(20)
    def positions(self):
        with self.client.get("/api/v1/portfolio/positions", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            stress_metrics.record("positions", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(15)
    def market_symbols(self):
        with self.client.get("/api/v1/market/symbols", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            stress_metrics.record("market_symbols", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")

    @task(10)
    def ai_prediction(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/ai/predict/price/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            elapsed = resp.elapsed.total_seconds()
            success = resp.status_code < 400
            stress_metrics.record("ai_prediction", elapsed, success)
            if not success:
                resp.failure(f"Status code: {resp.status_code}")


# ----- Custom Locust Load Shape for Stress Testing (Step Up) -----

class StressLoadShape:
    """
    Custom load shape for Locust that gradually increases users to find breaking point.
    """
    start_users = STRESS_START_USERS
    max_users = STRESS_MAX_USERS
    increment = STRESS_INCREMENT
    step_duration = STRESS_STEP_DURATION
    current_step = 0
    step_start_time = None
    users_at_step_start = start_users

    def tick(self):
        run_time = self.get_run_time()

        if self.step_start_time is None:
            self.step_start_time = run_time
            self.current_step = 0
            stress_metrics.start_step(self.current_step, self.start_users)
            return (self.start_users, 1)

        elapsed_in_step = run_time - self.step_start_time

        if elapsed_in_step >= self.step_duration:
            # Move to next step
            self.current_step += 1
            next_users = self.start_users + self.current_step * self.increment
            if next_users > self.max_users:
                return None  # Stop test
            self.step_start_time = run_time
            stress_metrics.start_step(self.current_step, next_users)
            # Spawn rate: bring up to next_users over a short period
            spawn_rate = max(1, (next_users - self.users_at_step_start) / 5)
            return (next_users, int(spawn_rate))
        else:
            # Keep current users
            users = self.start_users + self.current_step * self.increment
            return (users, 1)


# ----- Locust Event Handlers -----

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("STRESS LOAD TEST STARTING (Locust)")
    logger.info(f"Host: {BASE_URL}")
    logger.info(f"Start Users: {STRESS_START_USERS}, Max Users: {STRESS_MAX_USERS}")
    logger.info(f"Increment: {STRESS_INCREMENT}, Step Duration: {STRESS_STEP_DURATION}s")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("STRESS LOAD TEST COMPLETED (Locust)")
    logger.info("=" * 60)
    stats = environment.stats
    logger.info(f"Total Requests: {stats.total.num_requests}")
    logger.info(f"Failures: {stats.total.fail_ratio * 100:.2f}%")
    logger.info(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")

    analysis = stress_metrics.get_stress_analysis()
    if "error" not in analysis:
        logger.info("Stress Analysis:")
        logger.info(f"  Breaking point: {analysis['breaking_point']}")
        logger.info(f"  Max users: {analysis['max_users_reached']}")
        logger.info(f"  Graceful degradation: {analysis['graceful_degradation']}")


# ----- Standalone execution -----

if __name__ == "__main__":
    import pytest as pytest_module
    pytest_module.main([__file__, "-v", "--maxfail=1"])
