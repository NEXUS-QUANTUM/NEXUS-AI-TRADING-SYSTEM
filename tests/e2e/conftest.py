# tests/e2e/conftest.py
"""
E2E Test Configuration and Fixtures.

This file provides fixtures for end-to-end tests, including:
- Full application test client (async)
- Database setup and teardown
- Test user and authentication
- Pre-configured portfolios, orders, and broker accounts
- WebSocket client for real-time testing
- Mock external services (broker, market data, AI)
- Frontend testing support (Playwright, if installed)

All fixtures are designed to simulate real user interactions from start to finish.
"""

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Adjust imports according to project structure
from backend.main import app as backend_app
from backend.core.database import Base, get_async_db
from backend.core.security import create_access_token, get_password_hash
from backend.models.user import User
from backend.models.portfolio import Portfolio
from backend.models.broker_account import BrokerAccount
from backend.models.position import Position
from backend.models.order import Order
from backend.models.trade import Trade
from backend.models.subscription import Subscription, SubscriptionPlan
from backend.models.ai_model import AIModel, AIPrediction, AITraining
from backend.models.system_config import SystemConfig

# Test environment variables
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///./test_e2e.db")
os.environ["REDIS_URL"] = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")
os.environ["BROKER_ENVIRONMENT"] = "test"


# ============================== Database Fixtures ==============================

@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Return the test database URL."""
    return os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def test_db_engine(test_db_url: str):
    """Create a synchronous test database engine for e2e tests."""
    engine = create_engine(test_db_url.replace("+aiosqlite", ""), connect_args={"check_same_thread": False})
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_db_engine):
    """Provide a synchronous database session for e2e tests."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest_asyncio.fixture(scope="function")
async def async_db_engine(test_db_url: str):
    """Create an asynchronous test database engine."""
    engine = create_async_engine(test_db_url, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_db_session(async_db_engine):
    """Provide an asynchronous database session for async e2e tests."""
    async_session_factory = async_sessionmaker(async_db_engine, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session
        await session.rollback()
        await session.close()


# Override the async DB dependency for the app
def override_get_async_db():
    """Override the dependency to use the test async session."""
    async for session in async_db_session():
        yield session


# ============================== Test Client Fixtures ==============================

@pytest.fixture(scope="module")
def app():
    """Return the FastAPI application instance for e2e testing."""
    # Apply dependency overrides
    backend_app.dependency_overrides[get_async_db] = override_get_async_db
    return backend_app


@pytest.fixture(scope="function")
def sync_client(app):
    """Return a synchronous TestClient for e2e tests."""
    with TestClient(app) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Return an async HTTP client for e2e tests."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ============================== Authentication Fixtures ==============================

@pytest.fixture(scope="function")
def test_user_data() -> Dict[str, Any]:
    """Return default user data for e2e test user creation."""
    return {
        "email": "e2e_user@nexustradingia.com",
        "username": "e2e_user",
        "password": "E2EPass123!",
        "full_name": "E2E Test User",
        "is_active": True,
        "is_superuser": False,
        "is_verified": True,
    }


@pytest.fixture(scope="function")
def test_admin_data() -> Dict[str, Any]:
    """Return default admin user data for e2e tests."""
    return {
        "email": "e2e_admin@nexustradingia.com",
        "username": "e2e_admin",
        "password": "E2EAdmin123!",
        "full_name": "E2E Admin",
        "is_active": True,
        "is_superuser": True,
        "is_verified": True,
    }


@pytest.fixture(scope="function")
def test_user(db_session, test_user_data) -> User:
    """Create a test user in the database."""
    user = User(
        email=test_user_data["email"],
        username=test_user_data["username"],
        hashed_password=get_password_hash(test_user_data["password"]),
        full_name=test_user_data["full_name"],
        is_active=test_user_data["is_active"],
        is_superuser=test_user_data["is_superuser"],
        is_verified=test_user_data["is_verified"],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_admin(db_session, test_admin_data) -> User:
    """Create a test admin user."""
    user = User(
        email=test_admin_data["email"],
        username=test_admin_data["username"],
        hashed_password=get_password_hash(test_admin_data["password"]),
        full_name=test_admin_data["full_name"],
        is_active=test_admin_data["is_active"],
        is_superuser=test_admin_data["is_superuser"],
        is_verified=test_admin_data["is_verified"],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def access_token(test_user) -> str:
    """Generate an access token for the test user."""
    return create_access_token({"sub": str(test_user.id), "email": test_user.email})


@pytest.fixture(scope="function")
def refresh_token(test_user) -> str:
    """Generate a refresh token for the test user."""
    return create_access_token({"sub": str(test_user.id)}, refresh=True)


@pytest.fixture(scope="function")
def admin_access_token(test_admin) -> str:
    """Generate an access token for the admin user."""
    return create_access_token({"sub": str(test_admin.id), "email": test_admin.email})


# ============================== Test Data Fixtures ==============================

@pytest.fixture(scope="function")
def test_portfolio(db_session, test_user) -> Portfolio:
    """Create a test portfolio for the e2e test user."""
    portfolio = Portfolio(
        user_id=test_user.id,
        name="E2E Portfolio",
        description="Portfolio for end-to-end tests",
        is_active=True,
    )
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)
    return portfolio


@pytest.fixture(scope="function")
def test_broker_account(db_session, test_user) -> BrokerAccount:
    """Create a test broker account for the e2e test user."""
    account = BrokerAccount(
        user_id=test_user.id,
        broker_name="binance",
        account_id="e2e_broker_acc",
        api_key="e2e_api_key",
        api_secret_encrypted="e2e_encrypted_secret",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture(scope="function")
def test_position(db_session, test_portfolio) -> Position:
    """Create a test position for the e2e test portfolio."""
    position = Position(
        portfolio_id=test_portfolio.id,
        symbol="BTC-USD",
        quantity=0.5,
        avg_price=50000.0,
        current_price=51000.0,
        unrealized_pnl=500.0,
    )
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)
    return position


@pytest.fixture(scope="function")
def test_order(db_session, test_portfolio) -> Order:
    """Create a test order for the e2e test portfolio."""
    order = Order(
        portfolio_id=test_portfolio.id,
        symbol="BTC-USD",
        side="buy",
        order_type="market",
        quantity=0.5,
        price=50000.0,
        status="filled",
        filled_quantity=0.5,
        broker_order_id="e2e_broker_ord_123",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture(scope="function")
def test_subscription_plan(db_session) -> SubscriptionPlan:
    """Create a test subscription plan."""
    plan = SubscriptionPlan(
        name="E2E Pro Plan",
        description="Pro plan for e2e testing",
        price_monthly=99.99,
        price_yearly=999.99,
        features={"ai_predictions": True, "auto_trading": True},
        max_positions=50,
        max_portfolios=5,
        is_active=True,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.fixture(scope="function")
def test_subscription(db_session, test_user, test_subscription_plan) -> Subscription:
    """Create a test subscription for the e2e test user."""
    subscription = Subscription(
        user_id=test_user.id,
        plan_id=test_subscription_plan.id,
        status="active",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        auto_renew=True,
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(subscription)
    return subscription


# ============================== Mock Service Fixtures ==============================

@pytest.fixture(scope="function")
def mock_broker_service():
    """Provide a mock broker service for e2e tests."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.get_account = AsyncMock(return_value={"id": "mock_acc", "balance": 100000.0})
    mock.get_positions = AsyncMock(return_value=[])
    mock.place_order = AsyncMock(return_value={"id": "mock_ord", "status": "filled", "price": 50000.0})
    mock.get_market_data = AsyncMock(return_value=[{"open": 50000, "high": 51000, "low": 49000, "close": 50500, "volume": 1000}])
    mock.cancel_order = AsyncMock(return_value={"status": "cancelled"})
    return mock


@pytest.fixture(scope="function")
def mock_market_data_service():
    """Provide a mock market data service."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.get_historical_ohlcv = AsyncMock(return_value=[
        {"timestamp": 1609459200, "open": 50000, "high": 51000, "low": 49000, "close": 50500, "volume": 1000}
    ])
    mock.get_current_price = AsyncMock(return_value={"symbol": "BTC-USD", "price": 50500.0})
    return mock


@pytest.fixture(scope="function")
def mock_ai_prediction_service():
    """Provide a mock AI prediction service."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.predict = AsyncMock(return_value={"prediction": 0.6, "confidence": 0.85, "price": 51000.0})
    return mock


# ============================== WebSocket Fixtures ==============================

@pytest.fixture(scope="function")
def websocket_client(sync_client, access_token: str):
    """Provide a WebSocket client for e2e tests."""
    with sync_client.websocket_connect(f"/ws?token={access_token}") as websocket:
        # Wait for connection confirmation
        data = websocket.receive_json()
        assert data.get("type") == "connection_established"
        yield websocket
        websocket.close()


# ============================== Frontend Testing (Playwright) ==============================

# Optional: if Playwright is installed, we can provide browser fixtures.
try:
    from playwright.async_api import Browser, Page, Playwright, async_playwright

    @pytest_asyncio.fixture(scope="session")
    async def playwright() -> AsyncGenerator[Playwright, None]:
        """Launch Playwright for browser testing."""
        async with async_playwright() as p:
            yield p

    @pytest_asyncio.fixture(scope="session")
    async def browser(playwright: Playwright) -> AsyncGenerator[Browser, None]:
        """Launch a browser instance for e2e frontend tests."""
        browser = await playwright.chromium.launch(headless=True)
        yield browser
        await browser.close()

    @pytest_asyncio.fixture(scope="function")
    async def page(browser: Browser) -> AsyncGenerator[Page, None]:
        """Create a new page for each test."""
        context = await browser.new_context()
        page = await context.new_page()
        yield page
        await context.close()

except ImportError:
    # If Playwright not installed, skip frontend tests.
    pass


# ============================== Cleanup Fixtures ==============================

@pytest.fixture(autouse=True)
def clean_up_e2e_state():
    """Clean up any test state after each e2e test."""
    yield
    # The database is rolled back per session, and we can also clean up any temp files.
    # Additional cleanup can be added here if needed.


# ============================== Main Test Configuration ==============================

# Override the get_async_db dependency for the app.
# This ensures that all tests use the test database.
# The override is applied in the `app` fixture.

# We can also add a fixture to seed test data globally if needed.

@pytest.fixture(scope="session")
def seed_test_data(db_session):
    """Seed the test database with initial data for e2e tests (if needed)."""
    # Example: create a system config
    config = SystemConfig(key="e2e_seeded", value="true")
    db_session.add(config)
    db_session.commit()
