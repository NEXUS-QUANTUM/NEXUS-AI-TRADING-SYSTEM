# tests/backend/conftest.py
"""
Pytest configuration and shared fixtures for backend tests.

This file provides fixtures for:
- Database connection and session management (async)
- FastAPI test client with dependency overrides
- Authentication tokens (JWT)
- Mock broker, market data, and external services
- Test data factories (users, portfolios, orders, etc.)
- Configuration loading for test environment

All fixtures are designed to be used with pytest-asyncio for async tests.
"""

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Adjust imports according to the actual project structure
from backend.api.dependencies import get_current_user, get_db, get_async_db
from backend.core.config import settings
from backend.core.database import Base, get_db as original_get_db, get_async_db as original_get_async_db
from backend.core.security import create_access_token, create_refresh_token, get_password_hash
from backend.models.user import User
from backend.models.broker_account import BrokerAccount
from backend.models.portfolio import Portfolio
from backend.models.position import Position
from backend.models.order import Order
from backend.models.trade import Trade
from backend.models.subscription import Subscription, SubscriptionPlan
from backend.models.ai_model import AIModel, AIPrediction, AITraining
from backend.models.system_config import SystemConfig

# Test environment variables
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ["REDIS_URL"] = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")


# ---------------------------- Database Fixtures ----------------------------

@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Return the test database URL."""
    return os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def test_db_engine(test_db_url: str):
    """Create a synchronous test database engine."""
    engine = create_engine(test_db_url.replace("+aiosqlite", ""), connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_db_engine):
    """Provide a synchronous database session for tests."""
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
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_db_session(async_db_engine):
    """Provide an asynchronous database session for async tests."""
    async_session_factory = async_sessionmaker(async_db_engine, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session
        await session.rollback()
        await session.close()


# Override the database dependency for FastAPI
def override_get_db():
    """Override synchronous DB dependency."""
    db = next(db_session())
    try:
        yield db
    finally:
        db.close()


def override_get_async_db():
    """Override asynchronous DB dependency."""
    async for session in async_db_session():
        yield session


# ---------------------------- Test Client Fixtures ----------------------------

@pytest.fixture(scope="module")
def app():
    """Return the FastAPI application instance for testing."""
    from backend.main import app as application
    # Apply dependency overrides
    application.dependency_overrides[original_get_db] = override_get_db
    application.dependency_overrides[original_get_async_db] = override_get_async_db
    return application


@pytest.fixture(scope="function")
def client(app):
    """Return a TestClient for synchronous requests."""
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture(scope="function")
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Return an async HTTP client for async tests."""
    async with AsyncClient(app=app, base_url="http://test") as async_test_client:
        yield async_test_client


# ---------------------------- Authentication Fixtures ----------------------------

@pytest.fixture(scope="function")
def test_user_data() -> Dict[str, Any]:
    """Return default user data for test user creation."""
    return {
        "email": "testuser@nexustradingia.com",
        "username": "testuser",
        "password": "TestPassword123!",
        "full_name": "Test User",
        "is_active": True,
        "is_superuser": False,
        "is_verified": True,
    }


@pytest.fixture(scope="function")
def test_admin_data() -> Dict[str, Any]:
    """Return default admin user data."""
    return {
        "email": "admin@nexustradingia.com",
        "username": "admin",
        "password": "AdminPass123!",
        "full_name": "Admin User",
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
    """Create a test admin user in the database."""
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
    return create_refresh_token({"sub": str(test_user.id)})


@pytest.fixture(scope="function")
def admin_access_token(test_admin) -> str:
    """Generate an access token for the admin user."""
    return create_access_token({"sub": str(test_admin.id), "email": test_admin.email})


# Dependency override for authentication
def override_get_current_user(db_session, test_user):
    """Override the get_current_user dependency to always return the test user."""
    async def override():
        return test_user
    return override


# ---------------------------- Mock Services Fixtures ----------------------------

@pytest.fixture(scope="function")
def mock_broker_service():
    """Provide a mock broker service for testing."""
    from unittest.mock import AsyncMock, MagicMock
    mock = AsyncMock()
    mock.get_account = AsyncMock(return_value={"id": "acc123", "balance": 10000.0})
    mock.get_positions = AsyncMock(return_value=[])
    mock.place_order = AsyncMock(return_value={"id": "ord123", "status": "filled"})
    mock.get_market_data = AsyncMock(return_value={"price": 100.0, "volume": 1000})
    return mock


@pytest.fixture(scope="function")
def mock_market_data_service():
    """Provide a mock market data service."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.get_historical_ohlcv = AsyncMock(return_value=[])
    mock.get_current_price = AsyncMock(return_value={"symbol": "BTC-USD", "price": 50000.0})
    mock.get_order_book = AsyncMock(return_value={"bids": [], "asks": []})
    return mock


@pytest.fixture(scope="function")
def mock_ai_prediction_service():
    """Provide a mock AI prediction service."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.predict = AsyncMock(return_value={"prediction": 0.5, "confidence": 0.8})
    mock.train = AsyncMock(return_value={"status": "completed"})
    return mock


@pytest.fixture(scope="function")
def mock_risk_engine():
    """Provide a mock risk engine."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.check_risk = AsyncMock(return_value={"allowed": True, "reason": "OK"})
    mock.calculate_position_size = AsyncMock(return_value=1000.0)
    return mock


# ---------------------------- Test Data Factories ----------------------------

@pytest.fixture(scope="function")
def test_broker_account(db_session, test_user) -> BrokerAccount:
    """Create a test broker account for the test user."""
    account = BrokerAccount(
        user_id=test_user.id,
        broker_name="binance",
        account_id="test_acc_123",
        api_key="test_api_key",
        api_secret_encrypted="encrypted_secret",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture(scope="function")
def test_portfolio(db_session, test_user) -> Portfolio:
    """Create a test portfolio for the test user."""
    portfolio = Portfolio(
        user_id=test_user.id,
        name="Test Portfolio",
        description="Portfolio for testing",
        is_active=True,
    )
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)
    return portfolio


@pytest.fixture(scope="function")
def test_position(db_session, test_portfolio) -> Position:
    """Create a test position in the portfolio."""
    position = Position(
        portfolio_id=test_portfolio.id,
        symbol="BTC-USD",
        quantity=1.0,
        avg_price=50000.0,
        current_price=51000.0,
        unrealized_pnl=1000.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)
    return position


@pytest.fixture(scope="function")
def test_order(db_session, test_portfolio, test_position) -> Order:
    """Create a test order."""
    order = Order(
        portfolio_id=test_portfolio.id,
        symbol="BTC-USD",
        side="buy",
        order_type="limit",
        quantity=0.5,
        price=49000.0,
        status="filled",
        filled_quantity=0.5,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture(scope="function")
def test_trade(db_session, test_order) -> Trade:
    """Create a test trade associated with an order."""
    trade = Trade(
        order_id=test_order.id,
        symbol="BTC-USD",
        side="buy",
        quantity=0.5,
        price=49000.0,
        fee=10.0,
        trade_time=datetime.utcnow(),
    )
    db_session.add(trade)
    db_session.commit()
    db_session.refresh(trade)
    return trade


@pytest.fixture(scope="function")
def test_subscription_plan(db_session) -> SubscriptionPlan:
    """Create a test subscription plan."""
    plan = SubscriptionPlan(
        name="Pro Plan",
        description="Professional trading plan",
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
    """Create a test subscription for the test user."""
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


# ---------------------------- Configuration Fixtures ----------------------------

@pytest.fixture(scope="session")
def test_settings():
    """Return a settings object configured for testing."""
    from backend.core.config import Settings
    return Settings(
        ENVIRONMENT="test",
        DATABASE_URL=os.environ["DATABASE_URL"],
        REDIS_URL=os.environ["REDIS_URL"],
        JWT_SECRET_KEY="test_jwt_secret_key",
        JWT_ALGORITHM="HS256",
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES=5,
        JWT_REFRESH_TOKEN_EXPIRE_DAYS=1,
        BROKER_API_KEYS={"binance": {"api_key": "test", "api_secret": "test"}},
        # Add any other settings needed for tests
    )


@pytest.fixture(scope="function")
def temp_config_file() -> Generator[Path, None, None]:
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
        tf.write("test: true\n")
        tf.flush()
        yield Path(tf.name)
    Path(tf.name).unlink(missing_ok=True)


# ---------------------------- Utility Fixtures ----------------------------

@pytest.fixture(scope="function")
def event_loop():
    """Override the event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Fixture to clean up any test data after each test
@pytest.fixture(autouse=True)
def clean_up(db_session):
    """Automatically clean up database after each test."""
    yield
    # No explicit cleanup needed as the session is rolled back,
    # but we can add logic to truncate tables if needed.


# ---------------------------- Main Test Configuration ----------------------------

# Override the get_current_user dependency for authenticated endpoints
# This can be applied selectively in tests using dependency overrides.

# We also define a mock for Redis if needed.
@pytest.fixture(scope="function")
def mock_redis():
    """Return a mock Redis client."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=True)
    mock.publish = AsyncMock(return_value=True)
    return mock


# Additional fixture to override Redis dependency in the app
# This would be used in conjunction with app.dependency_overrides.

# End of conftest.py
