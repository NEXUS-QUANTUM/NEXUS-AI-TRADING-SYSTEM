"""
tests/load/conftest.py

NEXUS AI Trading System - Load Test Configuration

This module provides configuration and fixtures for load testing.
It supports both Locust-based distributed load testing and pytest-based
performance tests using the locust plugin.

Fixtures include:
- Test client for API load testing
- Authentication tokens for realistic user simulation
- Test data generation for realistic load scenarios
- Environment configuration for load test parameters
- Database reset/cleanup hooks for repeatable tests

The load tests can be run against a deployed staging or production environment,
or against a local test server with the --use-real-db flag.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
import random
import string
from typing import Dict, Any, Generator, Optional
from datetime import datetime, timedelta

# Load environment variables from .env file
from dotenv import load_dotenv

# For locust integration
from locust import HttpUser, task, between
from locust.exception import StopUser

# For API client in pytest-based load tests
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import get_db, SessionLocal
from backend.models.user import User
from backend.models.portfolio import Portfolio
from backend.security.auth import create_access_token

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Environment variables with defaults
BASE_URL = os.getenv("NEXUS_LOAD_TEST_BASE_URL", "http://localhost:8000")
API_URL = os.getenv("NEXUS_LOAD_TEST_API_URL", "http://localhost:8000/api/v1")
TEST_USER_EMAIL = os.getenv("LOAD_TEST_USER_EMAIL", "loadtest@nexusquantum.com")
TEST_USER_PASSWORD = os.getenv("LOAD_TEST_USER_PASSWORD", "LoadTest@123")
NUM_TEST_USERS = int(os.getenv("LOAD_TEST_NUM_USERS", "10"))

# Load test parameters
LOAD_TEST_DURATION = int(os.getenv("LOAD_TEST_DURATION", "300"))  # seconds
LOAD_TEST_USERS = int(os.getenv("LOAD_TEST_USERS", "50"))
LOAD_TEST_SPAWN_RATE = int(os.getenv("LOAD_TEST_SPAWN_RATE", "5"))

# Database configuration for load tests (if using a dedicated test DB)
LOAD_TEST_DATABASE_URL = os.getenv("LOAD_TEST_DATABASE_URL", "sqlite:///./load_test.db")


# ----- Pytest configuration -----

def pytest_configure(config):
    """Register custom markers for load tests."""
    config.addinivalue_line("markers", "load: mark test as load/performance test")
    config.addinivalue_line("markers", "smoke_load: mark test as smoke load test")
    config.addinivalue_line("markers", "stress: mark test as stress test")


def pytest_addoption(parser):
    """Add command-line options for load tests."""
    parser.addoption(
        "--load-duration",
        type=int,
        default=LOAD_TEST_DURATION,
        help="Duration of load test in seconds",
    )
    parser.addoption(
        "--load-users",
        type=int,
        default=LOAD_TEST_USERS,
        help="Number of simulated users",
    )
    parser.addoption(
        "--spawn-rate",
        type=int,
        default=LOAD_TEST_SPAWN_RATE,
        help="Rate of user spawning per second",
    )
    parser.addoption(
        "--use-real-db",
        action="store_true",
        default=False,
        help="Use real database instead of test DB",
    )


# ----- Locust user configuration -----

class NexusLoadTestUser(HttpUser):
    """
    Base Locust user class for NEXUS load testing.
    Implements authentication and common headers.
    """
    host = BASE_URL
    wait_time = between(1, 3)  # Think time between tasks
    token = None
    user_id = None

    def on_start(self):
        """Authenticate once per user session."""
        # Register or login
        # We'll try to login first; if fails, register a new user
        email = f"load_user_{self.environment.runner.user_count}_{random.randint(1000, 9999)}@nexusquantum.com"
        password = "LoadTest@123"

        # Try to register
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Load",
                "last_name": f"User_{random.randint(1000, 9999)}",
            },
            name="/auth/register",
        )
        if response.status_code == 201:
            # Registration successful
            self.token = response.json().get("access_token")
            self.user_id = response.json().get("id")
            logger.info(f"Registered load user {email} (ID: {self.user_id})")
        else:
            # Try to login with existing test user
            response = self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": TEST_USER_EMAIL,
                    "password": TEST_USER_PASSWORD,
                },
                name="/auth/login",
            )
            if response.status_code == 200:
                self.token = response.json().get("access_token")
                # We don't have user_id from login; we'll fetch it
                user_response = self.client.get(
                    "/api/v1/users/me",
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                if user_response.status_code == 200:
                    self.user_id = user_response.json().get("id")
                logger.info(f"Logged in as {TEST_USER_EMAIL}")
            else:
                logger.error("Failed to authenticate load user")
                raise StopUser()

    def on_stop(self):
        """Cleanup: logout (optional)."""
        if self.token:
            self.client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {self.token}"},
            )

    def get_headers(self):
        """Return headers with authorization token."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }


# ----- Fixtures for pytest-based load tests -----

@pytest.fixture(scope="session")
def load_test_config(request):
    """Provide load test configuration from command line or env."""
    return {
        "duration": request.config.getoption("--load-duration"),
        "users": request.config.getoption("--load-users"),
        "spawn_rate": request.config.getoption("--spawn-rate"),
        "use_real_db": request.config.getoption("--use-real-db"),
    }


@pytest.fixture(scope="session")
def load_test_client() -> Generator[TestClient, None, None]:
    """
    Create a TestClient for load testing the API directly.
    This uses the real FastAPI app with dependency overrides for test DB.
    """
    # Override database dependency to use test DB
    from backend.core.database import Base, engine
    from backend.core.config import settings

    # Create test database engine if not using real DB
    if not os.getenv("LOAD_TEST_USE_REAL_DB"):
        # Use SQLite in-memory or file for load tests
        test_engine = create_engine(LOAD_TEST_DATABASE_URL, pool_size=20, max_overflow=40)
        Base.metadata.create_all(bind=test_engine)
        # Override get_db
        def override_get_db():
            db = SessionLocal(bind=test_engine)
            try:
                yield db
            finally:
                db.close()
        app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    yield client

    # Cleanup
    app.dependency_overrides.clear()
    if not os.getenv("LOAD_TEST_USE_REAL_DB"):
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def load_test_user(load_test_client: TestClient) -> Dict[str, Any]:
    """
    Create a new test user for load testing.
    Returns user info including email, password, token, and user_id.
    """
    # Generate unique email
    email = f"loadtest_{int(datetime.utcnow().timestamp())}_{random.randint(1000, 9999)}@nexusquantum.com"
    password = "LoadTest@123"
    first_name = "Load"
    last_name = f"User_{random.randint(1000, 9999)}"

    # Register via API
    response = load_test_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
        },
    )
    if response.status_code != 201:
        # Fallback to existing test user
        email = TEST_USER_EMAIL
        password = TEST_USER_PASSWORD
        login_resp = load_test_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200, "Failed to authenticate load user"
        token = login_resp.json().get("access_token")
        # Get user_id
        me_resp = load_test_client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me_resp.json().get("id") if me_resp.status_code == 200 else None
        return {
            "email": email,
            "password": password,
            "token": token,
            "user_id": user_id,
        }

    data = response.json()
    # Login to get token
    login_resp = load_test_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json().get("access_token")
    return {
        "email": email,
        "password": password,
        "token": token,
        "user_id": data.get("id"),
    }


@pytest.fixture(scope="function")
def load_test_auth_headers(load_test_user: Dict[str, Any]) -> Dict[str, str]:
    """Return headers for authenticated load test user."""
    return {"Authorization": f"Bearer {load_test_user['token']}"}


@pytest.fixture(scope="function")
def load_test_portfolio(load_test_client: TestClient, load_test_auth_headers: Dict) -> Dict[str, Any]:
    """Get or create a portfolio for the load test user."""
    response = load_test_client.get("/api/v1/portfolio/summary", headers=load_test_auth_headers)
    if response.status_code == 200:
        return response.json()
    # If no portfolio, create one (portfolio is auto-created on registration, so this should not happen)
    # We'll attempt to create one via a broker connection
    # But we'll just skip; the test will fail if portfolio doesn't exist.
    return {"id": None}


# ----- Helper functions for load test data generation -----

def generate_random_symbol() -> str:
    """Generate a random stock symbol for load testing."""
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "SPY", "QQQ"]
    return random.choice(symbols)


def generate_random_order() -> Dict[str, Any]:
    """Generate a random order payload for load testing."""
    side = random.choice(["buy", "sell"])
    order_type = random.choice(["market", "limit"])
    quantity = random.randint(1, 100)
    symbol = generate_random_symbol()
    payload = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "order_type": order_type,
    }
    if order_type == "limit":
        # Generate a limit price around current price (we'll use a dummy price)
        payload["limit_price"] = round(random.uniform(100, 500), 2)
    return payload


def generate_random_watchlist() -> List[str]:
    """Generate a random list of symbols for watchlist."""
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "SPY", "QQQ"]
    return random.sample(symbols, random.randint(3, 8))


# ----- Locust events (optional) -----

def setup_load_test_environment():
    """Run once before any load test starts."""
    logger.info("Setting up load test environment...")
    # Could pre-populate test data, create users, etc.
    # For now, just log


def teardown_load_test_environment():
    """Run once after load tests complete."""
    logger.info("Tearing down load test environment...")
    # Could clean up test data, delete users, etc.
    # For now, just log


# ----- Startup/Teardown hooks for locust -----

def on_start():
    """Called when Locust starts."""
    setup_load_test_environment()


def on_stop():
    """Called when Locust stops."""
    teardown_load_test_environment()
