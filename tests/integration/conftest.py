"""
tests/integration/conftest.py

NEXUS AI Trading System - Integration Test Configuration

This module provides shared fixtures and configuration for all integration tests.
It sets up the FastAPI test client, database connections, authentication,
and mocking infrastructure for external services.

Fixtures are scoped appropriately for test isolation and performance.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
import asyncio
import tempfile
from typing import Dict, Any, Generator, AsyncGenerator, Optional, Callable
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import json

# Database and SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

# FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Redis
import redis.asyncio as redis

# Celery
from celery import Celery

# Configuration
from backend.core.config import settings
from backend.core.database import Base, get_db
from backend.main import app
from backend.security.auth import create_access_token, create_refresh_token
from backend.models.user import User
from backend.models.broker_account import BrokerAccount
from backend.models.portfolio import Portfolio
from backend.models.position import Position
from backend.models.order import Order
from backend.models.ai_model import AIModel
from backend.models.subscription import Subscription, SubscriptionPlan

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables for test configuration
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")
TEST_BROKER_URL = os.getenv("TEST_BROKER_URL", "memory://localhost")

# Test user credentials
TEST_USER_EMAIL = "test@nexusquantum.com"
TEST_USER_PASSWORD = "Test@123"
TEST_USER_ID = "test-user-id-123"


# ----- Pytest configuration hooks -----

def pytest_configure(config):
    """Register custom markers for integration tests."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "db: mark test that requires database")
    config.addinivalue_line("markers", "async: mark test as asynchronous")
    config.addinivalue_line("markers", "broker: mark test that requires broker mock")
    config.addinivalue_line("markers", "celery: mark test that requires Celery worker")
    config.addinivalue_line("markers", "slow: mark test as slow (long-running)")
    config.addinivalue_line("markers", "smoke: mark test as smoke test")


def pytest_addoption(parser):
    """Add command-line options for integration tests."""
    parser.addoption(
        "--db-url",
        action="store",
        default=TEST_DATABASE_URL,
        help="Database URL for integration tests"
    )
    parser.addoption(
        "--keep-db",
        action="store_true",
        default=False,
        help="Keep database after test run (do not drop tables)"
    )
    parser.addoption(
        "--use-real-broker",
        action="store_true",
        default=False,
        help="Use real broker connections instead of mocks"
    )


# ----- Database fixtures -----

@pytest.fixture(scope="session")
def db_engine(request):
    """Create a SQLAlchemy engine for the test database."""
    db_url = request.config.getoption("--db-url")
    engine = create_engine(db_url, poolclass=NullPool, echo=False)
    return engine


@pytest.fixture(scope="session")
def test_db(db_engine, request):
    """Create all tables and return the engine."""
    # Create tables
    Base.metadata.create_all(bind=db_engine)
    logger.info("Test database tables created")
    yield db_engine
    # Drop tables after tests (unless --keep-db is used)
    if not request.config.getoption("--keep-db"):
        Base.metadata.drop_all(bind=db_engine)
        logger.info("Test database tables dropped")


@pytest.fixture(scope="function")
def db_session(test_db):
    """Create a new database session for each test function."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def override_get_db(db_session):
    """Override the dependency to use the test database session."""
    def _get_db():
        try:
            yield db_session
        finally:
            pass
    return _get_db


# ----- FastAPI test client fixtures -----

@pytest.fixture(scope="function")
def client(override_get_db):
    """Create a FastAPI TestClient with dependency overrides."""
    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def async_client(override_get_db):
    """Create an async HTTP client for testing."""
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ----- Authentication fixtures -----

@pytest.fixture(scope="function")
def test_user(db_session) -> User:
    """Create and return a test user."""
    user = User(
        id=TEST_USER_ID,
        email=TEST_USER_EMAIL,
        first_name="Test",
        last_name="User",
        hashed_password="$2b$12$...",  # You can generate a real hash or use plaintext in test
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow(),
    )
    # Set password using the service or directly
    # For simplicity, we'll use a known hash for "Test@123"
    from backend.security.auth import get_password_hash
    user.hashed_password = get_password_hash(TEST_USER_PASSWORD)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_user_token(test_user) -> str:
    """Generate an access token for the test user."""
    return create_access_token(data={"sub": test_user.id})


@pytest.fixture(scope="function")
def test_user_refresh_token(test_user) -> str:
    """Generate a refresh token for the test user."""
    return create_refresh_token(data={"sub": test_user.id})


@pytest.fixture(scope="function")
def auth_headers(test_user_token) -> Dict[str, str]:
    """Return headers with authorization token."""
    return {"Authorization": f"Bearer {test_user_token}"}


@pytest.fixture(scope="function")
def authenticated_client(client, auth_headers) -> TestClient:
    """Return a test client with authentication headers set."""
    # We'll use the client fixture and add headers manually in tests
    # Or we can create a wrapper; simpler to just have the headers fixture.
    # We'll just return the client; user can use auth_headers separately.
    return client


# ----- Test data fixtures -----

@pytest.fixture(scope="function")
def test_portfolio(db_session, test_user) -> Portfolio:
    """Create a test portfolio for the user."""
    portfolio = Portfolio(
        user_id=test_user.id,
        name="Test Portfolio",
        total_balance=100000.0,
        available_balance=100000.0,
        currency="USD",
        created_at=datetime.utcnow(),
    )
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)
    return portfolio


@pytest.fixture(scope="function")
def test_broker_account(db_session, test_user) -> BrokerAccount:
    """Create a test broker account."""
    broker_account = BrokerAccount(
        user_id=test_user.id,
        broker_type="alpaca",
        api_key="TEST_KEY",
        api_secret_encrypted="encrypted_secret",
        is_active=True,
        is_paper=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(broker_account)
    db_session.commit()
    db_session.refresh(broker_account)
    return broker_account


@pytest.fixture(scope="function")
def test_position(db_session, test_portfolio, test_broker_account) -> Position:
    """Create a test position."""
    position = Position(
        portfolio_id=test_portfolio.id,
        broker_account_id=test_broker_account.id,
        symbol="AAPL",
        quantity=10,
        entry_price=150.0,
        current_price=155.0,
        side="long",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)
    return position


@pytest.fixture(scope="function")
def test_order(db_session, test_portfolio, test_broker_account) -> Order:
    """Create a test order."""
    order = Order(
        portfolio_id=test_portfolio.id,
        broker_account_id=test_broker_account.id,
        symbol="AAPL",
        side="buy",
        order_type="market",
        quantity=5,
        filled_quantity=0,
        price=150.0,
        stop_price=None,
        limit_price=None,
        status="open",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


# ----- Redis fixtures -----

@pytest.fixture(scope="session")
async def redis_client():
    """Create a Redis client for testing."""
    client = redis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        await client.ping()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.warning(f"Redis not available: {e}; using mock Redis")
        # We can use fakeredis or skip; for now we'll use a mock
        from redis.asyncio import Redis
        # Use a simple in-memory mock if real Redis is not available
        # This is a naive approach; better to use fakeredis
        client = MagicMock()
    yield client
    if not isinstance(client, MagicMock):
        await client.flushdb()
        await client.close()


@pytest.fixture(scope="function")
def redis_mock():
    """Mock Redis client for tests that don't require real Redis."""
    with patch('backend.core.redis_client.redis_client', MagicMock()) as mock:
        yield mock


# ----- Celery fixtures -----

@pytest.fixture(scope="session")
def celery_config():
    """Configure Celery for testing (in-memory broker)."""
    return {
        "broker_url": "memory://",
        "result_backend": "memory://",
        "task_always_eager": True,
        "task_eager_propagates": True,
    }


@pytest.fixture(scope="session")
def celery_app(celery_config):
    """Create a Celery app for testing."""
    from backend.tasks.celery_app import celery_app as app
    app.conf.update(celery_config)
    return app


@pytest.fixture(scope="function")
def celery_worker(celery_app):
    """Create a Celery worker for testing (eager mode)."""
    # In eager mode, tasks run immediately, no worker needed.
    yield celery_app


# ----- Broker mocking fixtures -----

@pytest.fixture(scope="function")
def mock_alpaca_broker():
    """Mock the Alpaca broker for testing."""
    with patch('backend.brokers.alpaca.AlpacaBroker') as mock:
        # Set up mock methods
        mock_instance = mock.return_value
        mock_instance.get_account.return_value = {
            "id": "test-account",
            "cash": 100000.0,
            "portfolio_value": 100000.0,
            "buying_power": 100000.0,
        }
        mock_instance.get_positions.return_value = []
        mock_instance.place_order.return_value = {
            "id": "order-123",
            "symbol": "AAPL",
            "side": "buy",
            "qty": 1,
            "status": "filled",
        }
        mock_instance.get_historical_data.return_value = MagicMock()
        yield mock


@pytest.fixture(scope="function")
def mock_binance_broker():
    """Mock the Binance broker for testing."""
    with patch('backend.brokers.binance.BinanceBroker') as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_broker_factory(mock_alpaca_broker, mock_binance_broker):
    """Mock the broker factory to return mocked brokers."""
    with patch('backend.brokers.broker_factory.get_broker') as mock_factory:
        mock_factory.return_value = mock_alpaca_broker.return_value
        yield mock_factory


# ----- External API mocking fixtures -----

@pytest.fixture(scope="function")
def mock_market_data_api():
    """Mock external market data API calls."""
    with patch('backend.services.market_data.MarketDataService') as mock:
        mock_instance = mock.return_value
        mock_instance.get_price.return_value = 150.0
        mock_instance.get_historical_data.return_value = []
        mock_instance.get_order_book.return_value = {"bids": [], "asks": []}
        yield mock


@pytest.fixture(scope="function")
def mock_news_api():
    """Mock news/sentiment API calls."""
    with patch('backend.services.sentiment.SentimentAnalyzer') as mock:
        mock_instance = mock.return_value
        mock_instance.analyze.return_value = {"sentiment": "positive", "score": 0.8}
        yield mock


# ----- AI model fixtures -----

@pytest.fixture(scope="function")
def mock_ai_model():
    """Mock AI model loading and prediction."""
    with patch('backend.ai.prediction.model_loader.ModelLoader') as mock:
        mock_instance = mock.return_value
        mock_instance.predict.return_value = 160.0
        mock_instance.model = MagicMock()
        yield mock


# ----- Test environment fixtures -----

@pytest.fixture(scope="session")
def test_config():
    """Provide test-specific configuration overrides."""
    return {
        "testing": True,
        "debug": True,
        "log_level": "DEBUG",
        "rate_limit_enabled": False,
        "mock_external_apis": True,
        "use_paper_trading": True,
    }


@pytest.fixture(autouse=True)
def mock_external_services(request, test_config):
    """Automatically mock external services unless disabled."""
    if test_config.get("mock_external_apis", True):
        # Apply all mocks
        with patch.multiple(
            'backend.brokers.alpaca',
            AlpacaBroker=MagicMock(),
            create=True,
        ), patch.multiple(
            'backend.services.market_data',
            MarketDataService=MagicMock(),
            create=True,
        ), patch.multiple(
            'backend.services.sentiment',
            SentimentAnalyzer=MagicMock(),
            create=True,
        ):
            yield
    else:
        yield


# ----- Utility fixtures -----

@pytest.fixture(scope="function")
def temp_file():
    """Provide a temporary file for tests that need file I/O."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="function")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ----- Hooks for test setup/teardown -----

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test results for reporting."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


# ----- Helper functions for test assertions -----

def assert_response_ok(response, expected_status=200):
    """Assert that the response status is as expected and contains data."""
    assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"
    if response.content:
        data = response.json()
        assert data is not None
        return data
    return None


def assert_error_response(response, expected_status=400, error_code=None):
    """Assert that the response is an error with the expected status and code."""
    assert response.status_code == expected_status
    data = response.json()
    assert "detail" in data or "error" in data
    if error_code:
        assert data.get("code") == error_code or data.get("error_code") == error_code
    return data
