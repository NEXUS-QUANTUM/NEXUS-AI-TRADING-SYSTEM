"""
tests/load/test_load_mixed.py

NEXUS AI Trading System - Mixed Load Tests

This module simulates realistic mixed user behavior with different user profiles
and request patterns. It combines:

- Read-only operations (portfolio views, market data, history)
- Write operations (orders, settings updates)
- Heavy endpoints (historical data, analytics)
- Light endpoints (ping, status)
- Different user types (traders, viewers, admins)

The mixed load test provides a more realistic representation of production traffic.

Usage:
    pytest tests/load/test_load_mixed.py -v
    locust -f tests/load/test_load_mixed.py --host=http://localhost:8000

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import logging
import pytest
import statistics
import random
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
MIXED_DURATION = int(os.getenv("MIXED_DURATION", "600"))  # seconds (10 minutes by default)
MIXED_USERS = int(os.getenv("MIXED_USERS", "50"))
SPAWN_RATE = int(os.getenv("MIXED_SPAWN_RATE", "5"))
MIXED_RAMP_UP = int(os.getenv("MIXED_RAMP_UP", "60"))  # seconds to reach full load

# Performance thresholds (combined)
MIXED_THRESHOLDS = {
    "overall_avg": 1.0,
    "overall_p95": 2.5,
    "error_rate": 0.02,
    "throughput_min": 20,  # 20 req/s minimum
}

# User profiles with weights
USER_PROFILES = {
    "trader": {
        "weight": 40,
        "description": "Active trader: places orders, views portfolio, checks market data",
    },
    "viewer": {
        "weight": 35,
        "description": "Passive viewer: reads portfolio, market data, analytics",
    },
    "admin": {
        "weight": 15,
        "description": "Administrator: manages users, settings, system checks",
    },
    "api": {
        "weight": 10,
        "description": "API consumer: frequent market data and prediction requests",
    },
}

# Endpoints by user profile
ENDPOINTS = {
    "trader": [
        {"name": "portfolio_summary", "method": "GET", "path": "/portfolio/summary", "weight": 25},
        {"name": "market_quote", "method": "GET", "path": "/market/quote/AAPL", "weight": 20},
        {"name": "place_order", "method": "POST", "path": "/trading/orders", "weight": 15},
        {"name": "positions", "method": "GET", "path": "/portfolio/positions", "weight": 15},
        {"name": "open_orders", "method": "GET", "path": "/trading/orders/open", "weight": 10},
        {"name": "cancel_order", "method": "POST", "path": "/trading/orders/{order_id}/cancel", "weight": 5},
        {"name": "risk_limits", "method": "GET", "path": "/risk/limits", "weight": 5},
        {"name": "market_symbols", "method": "GET", "path": "/market/symbols", "weight": 5},
    ],
    "viewer": [
        {"name": "portfolio_summary", "method": "GET", "path": "/portfolio/summary", "weight": 30},
        {"name": "market_quote", "method": "GET", "path": "/market/quote/AAPL", "weight": 25},
        {"name": "positions", "method": "GET", "path": "/portfolio/positions", "weight": 20},
        {"name": "performance", "method": "GET", "path": "/portfolio/performance", "weight": 15},
        {"name": "market_symbols", "method": "GET", "path": "/market/symbols", "weight": 10},
        {"name": "historical_data", "method": "GET", "path": "/market/historical/AAPL", "weight": 10},
        {"name": "users_me", "method": "GET", "path": "/users/me", "weight": 10},
    ],
    "admin": [
        {"name": "users_list", "method": "GET", "path": "/admin/users", "weight": 20},
        {"name": "system_status", "method": "GET", "path": "/admin/status", "weight": 20},
        {"name": "system_metrics", "method": "GET", "path": "/admin/metrics", "weight": 15},
        {"name": "user_management", "method": "PUT", "path": "/admin/users/{user_id}", "weight": 10},
        {"name": "logs", "method": "GET", "path": "/admin/logs", "weight": 10},
        {"name": "config_management", "method": "POST", "path": "/admin/config", "weight": 5},
        {"name": "portfolio_summary", "method": "GET", "path": "/portfolio/summary", "weight": 10},
        {"name": "market_quote", "method": "GET", "path": "/market/quote/AAPL", "weight": 10},
    ],
    "api": [
        {"name": "market_quote", "method": "GET", "path": "/market/quote/AAPL", "weight": 30},
        {"name": "ai_prediction", "method": "GET", "path": "/ai/predict/price/AAPL", "weight": 25},
        {"name": "market_symbols", "method": "GET", "path": "/market/symbols", "weight": 20},
        {"name": "historical_data", "method": "GET", "path": "/market/historical/AAPL", "weight": 15},
        {"name": "portfolio_summary", "method": "GET", "path": "/portfolio/summary", "weight": 10},
    ],
}


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


def setup_test_user(session: requests.Session, profile: str = "trader") -> Dict[str, Any]:
    """Register or login a test user with a specific profile."""
    email = f"mixed_{profile}_{int(time.time())}_{random.randint(1000, 9999)}@nexusquantum.com"
    password = "LoadTest@123"

    # Try to register
    try:
        response = session.post(
            f"{API_URL}/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": profile.capitalize(),
                "last_name": "MixedLoad",
            },
            timeout=5,
        )
        if response.status_code == 201:
            token = response.json().get("access_token") or get_auth_token(session, email, password)
            return {"email": email, "password": password, "token": token, "profile": profile}
    except Exception:
        pass

    # Try to login with default
    default_email = os.getenv("TEST_USER_EMAIL", "test@nexusquantum.com")
    default_password = os.getenv("TEST_USER_PASSWORD", "Test@123")
    token = get_auth_token(session, default_email, default_password)
    if token:
        return {"email": default_email, "password": default_password, "token": token, "profile": profile}

    logger.error(f"Failed to authenticate {profile} user")
    return None


# ----- Metric Collector (global) -----

class MixedLoadMetrics:
    """Collect and analyze metrics for mixed load tests."""

    def __init__(self):
        self.lock = threading.Lock()
        self.response_times = {}  # endpoint -> list of (timestamp, time)
        self.error_counts = {}    # endpoint -> int
        self.total_requests = {}  # endpoint -> int
        self.start_time = None
        self.profile_counts = {}  # profile -> count

    def record(self, endpoint: str, elapsed: float, success: bool, profile: str = "unknown"):
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
            self.total_requests[endpoint] += 1
            if not success:
                self.error_counts[endpoint] += 1
            if profile not in self.profile_counts:
                self.profile_counts[profile] = 0
            self.profile_counts[profile] += 1

    def get_stats(self, endpoint: str = None) -> Dict[str, Any]:
        """Get statistics for an endpoint or overall."""
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
                    "profile_counts": self.profile_counts.copy(),
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


# Global metrics collector
mixed_metrics = MixedLoadMetrics()


# ----- Pytest-based Mixed Load Test -----

@pytest.mark.load
@pytest.mark.mixed
class TestMixedLoad:
    """Mixed load tests simulating different user profiles."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session and user (trader by default)."""
        self.session = create_session_with_retries()
        self.user = setup_test_user(self.session, profile="trader")
        assert self.user is not None, "Failed to set up test user"
        self.auth_headers = {"Authorization": f"Bearer {self.user['token']}"}
        self.results = defaultdict(list)
        # We'll keep a list of users with different profiles for more realistic mix
        # For pytest-based test, we'll just use a single user but vary endpoints.
        yield
        self.session.close()

    def _make_request(self, endpoint: dict, profile: str) -> Tuple[str, float, bool]:
        """Make a single request and return metric."""
        name = endpoint["name"]
        method = endpoint["method"]
        path = endpoint["path"]
        # Handle path parameters (e.g., {order_id})
        if "{order_id}" in path:
            # We'll use a dummy order_id; for real testing, we should have an open order.
            # For load testing, we'll use a random ID and expect 404; but we'll handle it.
            # Better to avoid dynamic paths or handle gracefully.
            # We'll skip dynamic paths for simplicity or use a fixed value.
            path = path.replace("{order_id}", "dummy-123")
        url = f"{API_URL}{path}"
        start = time.time()
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=self.auth_headers, timeout=10)
            elif method.upper() == "POST":
                # For order placement, we need a portfolio_id
                if name == "place_order":
                    # Get portfolio ID first (could be cached)
                    portfolio_resp = self.session.get(f"{API_URL}/portfolio/summary", headers=self.auth_headers, timeout=5)
                    if portfolio_resp.status_code == 200:
                        portfolio_id = portfolio_resp.json().get("id")
                        if portfolio_id:
                            payload = {
                                "symbol": "AAPL",
                                "side": "buy" if random.random() > 0.5 else "sell",
                                "quantity": random.randint(1, 10),
                                "order_type": random.choice(["market", "limit"]),
                                "portfolio_id": portfolio_id,
                            }
                            if payload["order_type"] == "limit":
                                payload["limit_price"] = round(random.uniform(100, 300), 2)
                            response = self.session.post(url, headers=self.auth_headers, json=payload, timeout=10)
                        else:
                            response = self.session.post(url, headers=self.auth_headers, timeout=10)
                    else:
                        response = self.session.post(url, headers=self.auth_headers, timeout=10)
                else:
                    response = self.session.post(url, headers=self.auth_headers, timeout=10)
            elif method.upper() == "PUT":
                response = self.session.put(url, headers=self.auth_headers, timeout=10)
            else:
                response = self.session.request(method, url, headers=self.auth_headers, timeout=10)
            elapsed = time.time() - start
            success = response.status_code < 400
            return (name, elapsed, success)
        except Exception:
            return (name, time.time() - start, False)

    def test_mixed_workload(self):
        """Run a mixed workload for a configured duration."""
        duration = MIXED_DURATION
        if os.getenv("CI", "false").lower() == "true":
            duration = min(duration, 120)  # 2 minutes in CI
            logger.info("Running in CI mode, reducing mixed test duration to 120s")

        logger.info(f"Starting mixed load test for {duration} seconds with {MIXED_USERS} simulated users")
        start_time = time.time()
        end_time = start_time + duration
        request_count = 0
        error_count = 0
        last_report_time = start_time

        # Select profile weighted
        profiles = list(USER_PROFILES.keys())
        profile_weights = [USER_PROFILES[p]["weight"] for p in profiles]
        total_weight = sum(profile_weights)

        # Map endpoints by profile
        profile_endpoints = {p: ENDPOINTS.get(p, []) for p in profiles}
        for p in profiles:
            if not profile_endpoints[p]:
                # Fallback to trader endpoints
                profile_endpoints[p] = ENDPOINTS["trader"]

        # Pre-compute weighted endpoint lists for each profile
        weighted_endpoints = {}
        for p, eps in profile_endpoints.items():
            weights = [ep["weight"] for ep in eps]
            total_ep_weight = sum(weights)
            weighted_endpoints[p] = list(zip(eps, weights, [total_ep_weight]*len(eps)))

        while time.time() < end_time:
            # Select a user profile
            r = random.random() * total_weight
            cumulative = 0
            selected_profile = profiles[-1]
            for p, w in zip(profiles, profile_weights):
                cumulative += w
                if r <= cumulative:
                    selected_profile = p
                    break

            # Select endpoint within that profile
            eps = weighted_endpoints[selected_profile]
            total_ep_weight = eps[0][2] if eps else 0
            if not eps:
                continue
            r2 = random.random() * total_ep_weight
            cumulative2 = 0
            selected_ep = eps[-1][0]
            for ep, w, tw in eps:
                cumulative2 += w
                if r2 <= cumulative2:
                    selected_ep = ep
                    break

            # Make the request
            name, elapsed, success = self._make_request(selected_ep, selected_profile)
            mixed_metrics.record(name, elapsed, success, selected_profile)

            request_count += 1
            if not success:
                error_count += 1

            # Report periodically
            now = time.time()
            if now - last_report_time >= SAMPLE_INTERVAL:
                self._report_metrics(now - start_time)
                last_report_time = now

            # Think time based on profile
            think_time = random.uniform(0.1, 0.5)
            time.sleep(think_time)

        # Final report
        logger.info("=" * 60)
        logger.info("MIXED LOAD TEST COMPLETED")
        logger.info(f"Duration: {time.time() - start_time:.2f}s")
        logger.info(f"Total requests: {request_count}")
        logger.info(f"Error rate: {error_count/request_count:.2%}")
        logger.info("=" * 60)

        stats = mixed_metrics.get_stats()
        logger.info(f"Overall avg: {stats['avg_response']*1000:.1f}ms")
        logger.info(f"Overall p95: {stats['p95_response']*1000:.1f}ms")
        logger.info(f"Profile counts: {stats['profile_counts']}")

        # Assert thresholds
        assert stats["avg_response"] < MIXED_THRESHOLDS["overall_avg"], \
            f"Average response {stats['avg_response']:.3f}s > threshold {MIXED_THRESHOLDS['overall_avg']}s"
        assert stats["p95_response"] < MIXED_THRESHOLDS["overall_p95"], \
            f"p95 response {stats['p95_response']:.3f}s > threshold {MIXED_THRESHOLDS['overall_p95']}s"
        assert stats["error_rate"] < MIXED_THRESHOLDS["error_rate"], \
            f"Error rate {stats['error_rate']:.2%} > threshold {MIXED_THRESHOLDS['error_rate']:.2%}"

    def _report_metrics(self, elapsed: float):
        """Log current metrics."""
        stats = mixed_metrics.get_stats()
        logger.info(f"[{elapsed:.0f}s] "
                    f"Avg: {stats['avg_response']*1000:.1f}ms, "
                    f"p95: {stats['p95_response']*1000:.1f}ms, "
                    f"Errors: {stats['error_rate']:.2%}, "
                    f"Total: {stats['total_requests']}")


# ----- Locust User Definitions for Different Profiles -----

class BaseMixedUser(HttpUser):
    """Base class for mixed users with authentication."""
    host = BASE_URL
    abstract = True
    wait_time = between(1, 3)
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


class TraderUser(BaseMixedUser):
    """Trader user profile."""
    wait_time = between(0.5, 2)

    def get_portfolio_id(self):
        # Cache portfolio ID for order placement
        if not hasattr(self, "_portfolio_id"):
            with self.client.get("/api/v1/portfolio/summary", headers=self.get_headers(), catch_response=True) as resp:
                if resp.status_code == 200:
                    self._portfolio_id = resp.json().get("id")
                else:
                    self._portfolio_id = None
        return self._portfolio_id

    @task(25)
    def portfolio_summary(self):
        with self.client.get("/api/v1/portfolio/summary", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("portfolio_summary", resp.elapsed.total_seconds(), resp.status_code < 400, "trader")

    @task(20)
    def market_quote(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("market_quote", resp.elapsed.total_seconds(), resp.status_code < 400, "trader")

    @task(15)
    def place_order(self):
        portfolio_id = self.get_portfolio_id()
        if not portfolio_id:
            return
        payload = {
            "symbol": "AAPL",
            "side": "buy" if random.random() > 0.5 else "sell",
            "quantity": random.randint(1, 10),
            "order_type": random.choice(["market", "limit"]),
            "portfolio_id": portfolio_id,
        }
        if payload["order_type"] == "limit":
            payload["limit_price"] = round(random.uniform(100, 300), 2)
        with self.client.post("/api/v1/trading/orders", json=payload, headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code not in [200, 201, 202]:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("place_order", resp.elapsed.total_seconds(), resp.status_code < 400, "trader")

    @task(15)
    def positions(self):
        with self.client.get("/api/v1/portfolio/positions", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("positions", resp.elapsed.total_seconds(), resp.status_code < 400, "trader")

    @task(10)
    def open_orders(self):
        with self.client.get("/api/v1/trading/orders/open", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("open_orders", resp.elapsed.total_seconds(), resp.status_code < 400, "trader")

    @task(10)
    def risk_limits(self):
        with self.client.get("/api/v1/risk/limits", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("risk_limits", resp.elapsed.total_seconds(), resp.status_code < 400, "trader")

    @task(5)
    def market_symbols(self):
        with self.client.get("/api/v1/market/symbols", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("market_symbols", resp.elapsed.total_seconds(), resp.status_code < 400, "trader")


class ViewerUser(BaseMixedUser):
    """Viewer user profile."""
    wait_time = between(1, 4)

    @task(30)
    def portfolio_summary(self):
        with self.client.get("/api/v1/portfolio/summary", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("portfolio_summary", resp.elapsed.total_seconds(), resp.status_code < 400, "viewer")

    @task(25)
    def market_quote(self):
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("market_quote", resp.elapsed.total_seconds(), resp.status_code < 400, "viewer")

    @task(20)
    def positions(self):
        with self.client.get("/api/v1/portfolio/positions", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("positions", resp.elapsed.total_seconds(), resp.status_code < 400, "viewer")

    @task(15)
    def performance(self):
        intervals = ["daily", "weekly"]
        periods = ["3m", "6m", "1y"]
        params = {
            "interval": random.choice(intervals),
            "period": random.choice(periods),
        }
        with self.client.get("/api/v1/portfolio/performance", params=params, headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("performance", resp.elapsed.total_seconds(), resp.status_code < 400, "viewer")

    @task(10)
    def historical_data(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        timeframe = random.choice(["1h", "1d"])
        limit = random.choice([100, 500])
        with self.client.get(f"/api/v1/market/historical/{symbol}", params={"timeframe": timeframe, "limit": limit}, headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("historical_data", resp.elapsed.total_seconds(), resp.status_code < 400, "viewer")

    @task(10)
    def users_me(self):
        with self.client.get("/api/v1/users/me", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("users_me", resp.elapsed.total_seconds(), resp.status_code < 400, "viewer")

    @task(10)
    def market_symbols(self):
        with self.client.get("/api/v1/market/symbols", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("market_symbols", resp.elapsed.total_seconds(), resp.status_code < 400, "viewer")


class AdminUser(BaseMixedUser):
    """Admin user profile."""
    wait_time = between(2, 5)

    @task(20)
    def users_list(self):
        with self.client.get("/api/v1/admin/users", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("users_list", resp.elapsed.total_seconds(), resp.status_code < 400, "admin")

    @task(20)
    def system_status(self):
        with self.client.get("/api/v1/admin/status", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("system_status", resp.elapsed.total_seconds(), resp.status_code < 400, "admin")

    @task(15)
    def system_metrics(self):
        with self.client.get("/api/v1/admin/metrics", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("system_metrics", resp.elapsed.total_seconds(), resp.status_code < 400, "admin")

    @task(10)
    def logs(self):
        with self.client.get("/api/v1/admin/logs", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("logs", resp.elapsed.total_seconds(), resp.status_code < 400, "admin")

    @task(10)
    def portfolio_summary(self):
        with self.client.get("/api/v1/portfolio/summary", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("portfolio_summary", resp.elapsed.total_seconds(), resp.status_code < 400, "admin")

    @task(10)
    def market_quote(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("market_quote", resp.elapsed.total_seconds(), resp.status_code < 400, "admin")

    @task(5)
    def user_management(self):
        # Simulate updating a user (we'll use a dummy user_id)
        with self.client.put(f"/api/v1/admin/users/dummy-user-id", json={"status": "active"}, headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code not in [200, 204]:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("user_management", resp.elapsed.total_seconds(), resp.status_code < 400, "admin")

    @task(5)
    def config_management(self):
        payload = {"key": "test_config", "value": "test_value"}
        with self.client.post("/api/v1/admin/config", json=payload, headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code not in [200, 201]:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("config_management", resp.elapsed.total_seconds(), resp.status_code < 400, "admin")


class APIUser(BaseMixedUser):
    """API consumer user profile."""
    wait_time = between(0.5, 1.5)

    @task(30)
    def market_quote(self):
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/market/quote/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("market_quote", resp.elapsed.total_seconds(), resp.status_code < 400, "api")

    @task(25)
    def ai_prediction(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        with self.client.get(f"/api/v1/ai/predict/price/{symbol}", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("ai_prediction", resp.elapsed.total_seconds(), resp.status_code < 400, "api")

    @task(20)
    def market_symbols(self):
        with self.client.get("/api/v1/market/symbols", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("market_symbols", resp.elapsed.total_seconds(), resp.status_code < 400, "api")

    @task(15)
    def historical_data(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        symbol = random.choice(symbols)
        timeframe = random.choice(["1h", "1d"])
        limit = random.choice([100, 500])
        with self.client.get(f"/api/v1/market/historical/{symbol}", params={"timeframe": timeframe, "limit": limit}, headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("historical_data", resp.elapsed.total_seconds(), resp.status_code < 400, "api")

    @task(10)
    def portfolio_summary(self):
        with self.client.get("/api/v1/portfolio/summary", headers=self.get_headers(), catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status code: {resp.status_code}")
            mixed_metrics.record("portfolio_summary", resp.elapsed.total_seconds(), resp.status_code < 400, "api")


# ----- Locust Event Handlers -----

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("MIXED LOAD TEST STARTING")
    logger.info(f"Host: {BASE_URL}")
    logger.info(f"Users: {MIXED_USERS}")
    logger.info(f"Spawn Rate: {SPAWN_RATE}/s")
    logger.info(f"Duration: {MIXED_DURATION}s")
    logger.info("Profiles: " + ", ".join(f"{p} ({w}%)" for p, w in [
        (p, USER_PROFILES[p]["weight"] / sum(x["weight"] for x in USER_PROFILES.values()) * 100)
        for p in USER_PROFILES.keys()
    ]))
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("MIXED LOAD TEST COMPLETED")
    logger.info("=" * 60)
    stats = environment.stats
    logger.info(f"Total Requests: {stats.total.num_requests}")
    logger.info(f"Failures: {stats.total.fail_ratio * 100:.2f}%")
    logger.info(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    logger.info(f"RPS (Total): {stats.total.total_rps:.2f}")

    # Overall metrics from our collector
    overall = mixed_metrics.get_stats()
    logger.info(f"Overall Avg: {overall['avg_response']*1000:.1f}ms")
    logger.info(f"Overall p95: {overall['p95_response']*1000:.1f}ms")
    logger.info(f"Profile counts: {overall['profile_counts']}")


# ----- Standalone execution -----

if __name__ == "__main__":
    import pytest as pytest_module
    pytest_module.main([__file__, "-v", "--maxfail=1"])
