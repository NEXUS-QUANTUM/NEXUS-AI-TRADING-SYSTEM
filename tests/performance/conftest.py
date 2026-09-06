"""
tests/performance/conftest.py

NEXUS AI Trading System - Performance Test Configuration

This module provides fixtures and configuration for performance/benchmark tests.
It uses pytest-benchmark to measure and compare performance of critical code paths,
API endpoints, and database operations.

Features:
- Benchmark fixtures for API endpoints
- Database session for performance testing
- Authentication tokens for realistic scenarios
- Test data generation with configurable volume
- Custom markers for categorizing performance tests
- Hooks for generating performance reports

Usage:
    pytest tests/performance -v --benchmark-autosave
    pytest tests/performance -v --benchmark-compare

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
import random
import string
import time
from typing import Dict, Any, Generator, Optional, Callable
from datetime import datetime, timedelta

# Database and SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

# FastAPI
from fastapi.testclient import TestClient

# Configuration
from backend.core.config import settings
from backend.core.database import Base, get_db
from backend.main import app
from backend.security.auth import create_access_token, create_refresh_token
from backend.models.user import User
from backend.models.portfolio import Portfolio
from backend.models.position import Position
from backend.models.order import Order
from backend.models.broker_account import BrokerAccount

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables for performance tests
PERF_DATABASE_URL = os.getenv("PERF_DATABASE_URL", "sqlite:///./perf_test.db")
PERF_NUM_USERS = int(os.getenv("PERF_NUM_USERS", "10"))
PERF_NUM_POSITIONS = int(os.getenv("PERF_NUM_POSITIONS", "50"))
PERF_NUM_ORDERS = int(os.getenv("PERF_NUM_ORDERS", "100"))

# Test user credentials
TEST_USER_EMAIL = "perf_test@nexusquantum.com"
TEST_USER_PASSWORD = "PerfTest@123"
TEST_USER_ID = "perf-test-user-123"


# ----- Pytest configuration hooks -----

def pytest_configure(config):
    """Register custom markers for performance tests."""
    config.addinivalue_line("markers", "perf: mark test as performance/benchmark test")
    config.addinivalue_line("markers", "api: mark test as API performance test")
    config.addinivalue_line("markers", "db: mark test as database performance test")
    config.addinivalue_line("markers", "slow: mark test as slow performance test")
    config.addinivalue_line("markers", "smoke_perf: mark test as smoke performance test")


def pytest_addoption(parser):
    """Add command-line options for performance tests."""
    parser.addoption(
        "--perf-db-url",
        action="store",
        default=PERF_DATABASE_URL,
        help="Database URL for performance tests"
    )
    parser.addoption(
        "--perf-num-users",
        type=int,
        default=PERF_NUM_USERS,
        help="Number of test users to create for performance tests"
    )
    parser.addoption(
        "--perf-num-positions",
        type=int,
        default=PERF_NUM_POSITIONS,
        help="Number of test positions to create per user"
    )
    parser.addoption(
        "--perf-num-orders",
        type=int,
        default=PERF_NUM_ORDERS,
        help="Number of test orders to create per user"
    )


# ----- Database fixtures -----

@pytest.fixture(scope="session")
def perf_db_engine(request):
    """Create a SQLAlchemy engine for the performance test database."""
    db_url = request.config.getoption("--perf-db-url")
    engine = create_engine(db_url, poolclass=NullPool, echo=False)
    return engine


@pytest.fixture(scope="session")
def perf_db(perf_db_engine):
    """Create all tables and return the engine."""
    Base.metadata.create_all(bind=perf_db_engine)
    logger.info("Performance test database tables created")
    yield perf_db_engine
    # Optionally drop tables after tests
    # Base.metadata.drop_all(bind=perf_db_engine)


@pytest.fixture(scope="function")
def perf_db_session(perf_db):
    """Create a new database session for each performance test function."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=perf_db)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ----- FastAPI test client fixtures -----

@pytest.fixture(scope="function")
def perf_client(perf_db_session):
    """Create a FastAPI TestClient with database override for performance tests."""
    def override_get_db():
        try:
            yield perf_db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ----- Authentication fixtures -----

@pytest.fixture(scope="function")
def perf_test_user(perf_db_session) -> User:
    """Create or retrieve a test user for performance tests."""
    # Check if user already exists
    user = perf_db_session.query(User).filter(User.email == TEST_USER_EMAIL).first()
    if not user:
        from backend.security.auth import get_password_hash
        user = User(
            id=TEST_USER_ID,
            email=TEST_USER_EMAIL,
            first_name="Perf",
            last_name="Test",
            hashed_password=get_password_hash(TEST_USER_PASSWORD),
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow(),
        )
        perf_db_session.add(user)
        perf_db_session.commit()
        perf_db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def perf_test_token(perf_test_user) -> str:
    """Generate an access token for the performance test user."""
    return create_access_token(data={"sub": perf_test_user.id})


@pytest.fixture(scope="function")
def perf_auth_headers(perf_test_token) -> Dict[str, str]:
    """Return headers with authorization token."""
    return {"Authorization": f"Bearer {perf_test_token}"}


# ----- Test data fixtures -----

@pytest.fixture(scope="function")
def perf_test_portfolio(perf_db_session, perf_test_user) -> Portfolio:
    """Create a test portfolio with significant data for performance testing."""
    portfolio = Portfolio(
        user_id=perf_test_user.id,
        name="Performance Test Portfolio",
        total_balance=1000000.0,
        available_balance=950000.0,
        currency="USD",
        created_at=datetime.utcnow(),
    )
    perf_db_session.add(portfolio)
    perf_db_session.commit()
    perf_db_session.refresh(portfolio)
    return portfolio


@pytest.fixture(scope="function")
def perf_test_broker(perf_db_session, perf_test_user) -> BrokerAccount:
    """Create a test broker account."""
    broker = BrokerAccount(
        user_id=perf_test_user.id,
        broker_type="alpaca",
        api_key="PERF_KEY",
        api_secret_encrypted="encrypted_secret",
        is_active=True,
        is_paper=True,
        created_at=datetime.utcnow(),
    )
    perf_db_session.add(broker)
    perf_db_session.commit()
    perf_db_session.refresh(broker)
    return broker


@pytest.fixture(scope="function")
def perf_test_positions(perf_db_session, perf_test_portfolio, perf_test_broker, request) -> List[Position]:
    """Create multiple test positions for performance testing."""
    num_positions = request.config.getoption("--perf-num-positions")
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "SPY", "QQQ"]
    positions = []
    for i in range(num_positions):
        symbol = random.choice(symbols)
        pos = Position(
            portfolio_id=perf_test_portfolio.id,
            broker_account_id=perf_test_broker.id,
            symbol=symbol,
            quantity=random.randint(1, 100),
            entry_price=random.uniform(50, 500),
            current_price=random.uniform(50, 500),
            side=random.choice(["long", "short"]),
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            updated_at=datetime.utcnow(),
        )
        positions.append(pos)
    perf_db_session.add_all(positions)
    perf_db_session.commit()
    # Refresh positions to get IDs
    for pos in positions:
        perf_db_session.refresh(pos)
    return positions


@pytest.fixture(scope="function")
def perf_test_orders(perf_db_session, perf_test_portfolio, perf_test_broker, request) -> List[Order]:
    """Create multiple test orders for performance testing."""
    num_orders = request.config.getoption("--perf-num-orders")
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "SPY", "QQQ"]
    statuses = ["open", "filled", "cancelled", "partially_filled"]
    orders = []
    for i in range(num_orders):
        symbol = random.choice(symbols)
        order = Order(
            portfolio_id=perf_test_portfolio.id,
            broker_account_id=perf_test_broker.id,
            symbol=symbol,
            side=random.choice(["buy", "sell"]),
            order_type=random.choice(["market", "limit", "stop"]),
            quantity=random.randint(1, 100),
            filled_quantity=0,
            price=random.uniform(50, 500),
            limit_price=random.uniform(50, 500) if random.random() > 0.5 else None,
            stop_price=random.uniform(50, 500) if random.random() > 0.5 else None,
            status=random.choice(statuses),
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            updated_at=datetime.utcnow(),
        )
        orders.append(order)
    perf_db_session.add_all(orders)
    perf_db_session.commit()
    for order in orders:
        perf_db_session.refresh(order)
    return orders


# ----- Benchmarking helper fixtures -----

@pytest.fixture(scope="function")
def perf_benchmark_rounds(request) -> int:
    """Return number of benchmark rounds from command line or default."""
    # The --benchmark-rounds is a standard pytest-benchmark option, but we can provide default.
    return request.config.getoption("--benchmark-rounds", default=10)


@pytest.fixture(scope="function")
def perf_benchmark_iterations(request) -> int:
    """Return number of benchmark iterations per round."""
    return request.config.getoption("--benchmark-iterations", default=1)


# ----- Data generation helpers -----

def generate_bulk_users(session: Session, count: int = 100) -> None:
    """Generate a large number of test users for performance testing."""
    users = []
    for i in range(count):
        email = f"perf_user_{i}_{int(time.time())}@example.com"
        from backend.security.auth import get_password_hash
        user = User(
            id=f"perf-user-{i}-{random.randint(1000, 9999)}",
            email=email,
            first_name=f"Perf{i}",
            last_name="User",
            hashed_password=get_password_hash("PerfTest@123"),
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow(),
        )
        users.append(user)
    session.bulk_save_objects(users)
    session.commit()
    logger.info(f"Generated {count} performance test users")


def generate_bulk_positions(session: Session, portfolio_id: str, broker_id: str, count: int = 200) -> None:
    """Generate a large number of positions for performance testing."""
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "SPY", "QQQ", "JPM", "V", "WMT", "JNJ", "PG"]
    positions = []
    for i in range(count):
        pos = Position(
            portfolio_id=portfolio_id,
            broker_account_id=broker_id,
            symbol=random.choice(symbols),
            quantity=random.randint(1, 1000),
            entry_price=random.uniform(10, 1000),
            current_price=random.uniform(10, 1000),
            side=random.choice(["long", "short"]),
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 365)),
            updated_at=datetime.utcnow(),
        )
        positions.append(pos)
    session.bulk_save_objects(positions)
    session.commit()


# ----- Custom performance report hooks -----

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture performance test results for reporting."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


# ----- Performance test environment fixture -----

@pytest.fixture(scope="session", autouse=True)
def perf_environment(request):
    """Set up performance test environment."""
    # Pre-populate data if needed
    # This can be controlled by a command-line option
    if request.config.getoption("--perf-num-users") > 0:
        # We could pre-generate users here
        pass
    yield
    # Teardown: cleanup if needed
    pass


# ----- Helpers for benchmarking -----

def benchmark_api_endpoint(client: TestClient, method: str, path: str, headers: Dict = None, data: Dict = None):
    """
    Helper to benchmark an API endpoint.
    Returns execution time and response status.
    """
    import time
    start = time.time()
    if method.upper() == "GET":
        response = client.get(path, headers=headers, params=data)
    elif method.upper() == "POST":
        response = client.post(path, headers=headers, json=data)
    elif method.upper() == "PUT":
        response = client.put(path, headers=headers, json=data)
    elif method.upper() == "DELETE":
        response = client.delete(path, headers=headers)
    else:
        response = client.request(method, path, headers=headers, json=data)
    elapsed = time.time() - start
    return elapsed, response.status_code, response.json() if response.status_code < 400 else None
