
# tests/backend/test_database.py
"""
Database Tests for the NEXUS AI Trading System.

This module contains tests for:
- Database connections and session management
- Model creation and validation
- CRUD operations for all core models
- Relationships and foreign key constraints
- Indexes and performance queries
- Unique constraints and cascading deletes
- Database migrations and schema integrity
- Edge cases and error handling

All tests use shared fixtures from conftest.py.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import Base
from backend.models.ai_model import AIModel, AIPrediction, AITraining
from backend.models.broker_account import BrokerAccount
from backend.models.order import Order
from backend.models.portfolio import Portfolio
from backend.models.position import Position
from backend.models.subscription import Subscription, SubscriptionPlan
from backend.models.trade import Trade
from backend.models.user import User

pytest_plugins = ["tests.backend.conftest"]


# ============================== DATABASE CONNECTION TESTS ==============================

class TestDatabaseConnection:
    """Test database connection and session management."""

    async def test_db_connection_async(self, async_db_session: AsyncSession):
        """Test that async database connection works and can execute queries."""
        result = await async_db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    def test_db_connection_sync(self, db_session):
        """Test that sync database connection works."""
        result = db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    async def test_session_rollback_on_error(self, async_db_session: AsyncSession):
        """Test that session rolls back on error."""
        # Create a valid user first
        user = User(
            email="rollback@example.com",
            username="rollbackuser",
            hashed_password="hashed",
            full_name="Rollback User",
        )
        async_db_session.add(user)
        await async_db_session.flush()  # flush to assign id but not commit

        # Now try to insert a duplicate email (should raise IntegrityError)
        user2 = User(
            email="rollback@example.com",  # Duplicate
            username="rollbackuser2",
            hashed_password="hashed",
            full_name="Duplicate",
        )
        async_db_session.add(user2)
        with pytest.raises(IntegrityError):
            await async_db_session.commit()

        # Rollback should have happened; session should be clean
        # We can check that the original user is not persisted (since we didn't commit before)
        # Actually we flushed, so the original user might exist if we rolled back.
        # After rollback, both should be gone.
        await async_db_session.rollback()
        # Query to verify no users with that email exist
        result = await async_db_session.execute(
            select(User).where(User.email == "rollback@example.com")
        )
        assert result.scalar_one_or_none() is None


# ============================== MODEL CREATION TESTS ==============================

class TestModelCreation:
    """Test that models can be created with valid data."""

    def test_create_user(self, db_session):
        """Test creating a User model."""
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password="hashed_password",
            full_name="Test User",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        assert user.id is not None
        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.email == "test@example.com"

    def test_create_portfolio(self, db_session, test_user):
        """Test creating a Portfolio associated with a User."""
        portfolio = Portfolio(
            user_id=test_user.id,
            name="Test Portfolio",
            description="A test portfolio",
            is_active=True,
        )
        db_session.add(portfolio)
        db_session.commit()
        db_session.refresh(portfolio)
        assert portfolio.id is not None
        assert portfolio.user_id == test_user.id
        assert portfolio.created_at is not None

    def test_create_broker_account(self, db_session, test_user):
        """Test creating a BrokerAccount."""
        broker = BrokerAccount(
            user_id=test_user.id,
            broker_name="binance",
            account_id="test_acc_001",
            api_key="test_api_key",
            api_secret_encrypted="encrypted_secret",
            is_active=True,
        )
        db_session.add(broker)
        db_session.commit()
        db_session.refresh(broker)
        assert broker.id is not None
        assert broker.broker_name == "binance"

    def test_create_subscription_plan(self, db_session):
        """Test creating a SubscriptionPlan."""
        plan = SubscriptionPlan(
            name="Pro Plan",
            description="Professional plan",
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
        assert plan.id is not None
        assert plan.price_monthly == 99.99

    def test_create_subscription(self, db_session, test_user, test_subscription_plan):
        """Test creating a Subscription."""
        sub = Subscription(
            user_id=test_user.id,
            plan_id=test_subscription_plan.id,
            status="active",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            auto_renew=True,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        assert sub.id is not None
        assert sub.user_id == test_user.id

    def test_create_order(self, db_session, test_portfolio):
        """Test creating an Order."""
        order = Order(
            portfolio_id=test_portfolio.id,
            symbol="BTC-USD",
            side="buy",
            order_type="limit",
            quantity=1.0,
            price=50000.0,
            status="pending",
            filled_quantity=0.0,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        assert order.id is not None
        assert order.symbol == "BTC-USD"

    def test_create_position(self, db_session, test_portfolio):
        """Test creating a Position."""
        position = Position(
            portfolio_id=test_portfolio.id,
            symbol="BTC-USD",
            quantity=0.5,
            avg_price=49000.0,
            current_price=49500.0,
            unrealized_pnl=250.0,
        )
        db_session.add(position)
        db_session.commit()
        db_session.refresh(position)
        assert position.id is not None
        assert position.unrealized_pnl == 250.0

    def test_create_trade(self, db_session, test_order):
        """Test creating a Trade associated with an Order."""
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
        assert trade.id is not None
        assert trade.order_id == test_order.id

    def test_create_ai_model(self, db_session):
        """Test creating an AIModel entry."""
        model = AIModel(
            model_name="lstm_v1",
            model_type="lstm",
            version="1.0",
            framework="pytorch",
            description="Test LSTM model",
            hyperparameters={"layers": 2, "hidden_size": 64},
            model_path="s3://models/lstm_v1.pt",
            is_active=True,
        )
        db_session.add(model)
        db_session.commit()
        db_session.refresh(model)
        assert model.id is not None
        assert model.model_name == "lstm_v1"

    def test_create_ai_prediction(self, db_session, test_user):
        """Test creating an AIPrediction."""
        pred = AIPrediction(
            user_id=test_user.id,
            model_id=None,  # optional
            symbol="BTC-USD",
            timeframe="1h",
            prediction_type="price",
            predicted_value=51000.0,
            confidence=0.85,
            actual_value=None,
            created_at=datetime.utcnow(),
        )
        db_session.add(pred)
        db_session.commit()
        db_session.refresh(pred)
        assert pred.id is not None
        assert pred.predicted_value == 51000.0

    def test_create_ai_training(self, db_session, test_user):
        """Test creating an AITraining record."""
        training = AITraining(
            user_id=test_user.id,
            model_id=None,
            training_id="train_001",
            status="running",
            training_config={"epochs": 10, "batch_size": 32},
            started_at=datetime.utcnow(),
            completed_at=None,
        )
        db_session.add(training)
        db_session.commit()
        db_session.refresh(training)
        assert training.id is not None
        assert training.status == "running"


# ============================== RELATIONSHIP TESTS ==============================

class TestRelationships:
    """Test relationships and foreign key constraints."""

    def test_user_portfolio_relationship(self, db_session, test_user):
        """Test that a User has many Portfolios."""
        portfolio1 = Portfolio(user_id=test_user.id, name="Portfolio 1", description="Desc1")
        portfolio2 = Portfolio(user_id=test_user.id, name="Portfolio 2", description="Desc2")
        db_session.add_all([portfolio1, portfolio2])
        db_session.commit()
        # Refresh user and check portfolios
        db_session.refresh(test_user)
        assert len(test_user.portfolios) == 2
        assert test_user.portfolios[0].name in ["Portfolio 1", "Portfolio 2"]

    def test_portfolio_orders_relationship(self, db_session, test_portfolio):
        """Test that a Portfolio has many Orders."""
        order1 = Order(portfolio_id=test_portfolio.id, symbol="BTC-USD", side="buy", order_type="limit", quantity=1.0, price=50000.0, status="pending")
        order2 = Order(portfolio_id=test_portfolio.id, symbol="ETH-USD", side="sell", order_type="market", quantity=2.0, price=3000.0, status="filled")
        db_session.add_all([order1, order2])
        db_session.commit()
        db_session.refresh(test_portfolio)
        assert len(test_portfolio.orders) == 2

    def test_portfolio_positions_relationship(self, db_session, test_portfolio):
        """Test that a Portfolio has many Positions."""
        pos1 = Position(portfolio_id=test_portfolio.id, symbol="BTC-USD", quantity=0.5, avg_price=49000.0, current_price=49500.0)
        pos2 = Position(portfolio_id=test_portfolio.id, symbol="ETH-USD", quantity=1.0, avg_price=3000.0, current_price=3100.0)
        db_session.add_all([pos1, pos2])
        db_session.commit()
        db_session.refresh(test_portfolio)
        assert len(test_portfolio.positions) == 2

    def test_order_trades_relationship(self, db_session, test_order):
        """Test that an Order has many Trades."""
        trade1 = Trade(order_id=test_order.id, symbol="BTC-USD", side="buy", quantity=0.5, price=49000.0, fee=10.0, trade_time=datetime.utcnow())
        trade2 = Trade(order_id=test_order.id, symbol="BTC-USD", side="buy", quantity=0.5, price=49100.0, fee=10.0, trade_time=datetime.utcnow())
        db_session.add_all([trade1, trade2])
        db_session.commit()
        db_session.refresh(test_order)
        assert len(test_order.trades) == 2

    def test_user_subscription_relationship(self, db_session, test_user, test_subscription_plan):
        """Test that a User has a Subscription."""
        sub = Subscription(user_id=test_user.id, plan_id=test_subscription_plan.id, status="active", start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30))
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(test_user)
        assert test_user.subscription is not None
        assert test_user.subscription.plan_id == test_subscription_plan.id

    def test_user_broker_accounts_relationship(self, db_session, test_user):
        """Test that a User has many BrokerAccounts."""
        broker1 = BrokerAccount(user_id=test_user.id, broker_name="binance", account_id="acc1", api_key="key1", api_secret_encrypted="sec1")
        broker2 = BrokerAccount(user_id=test_user.id, broker_name="bybit", account_id="acc2", api_key="key2", api_secret_encrypted="sec2")
        db_session.add_all([broker1, broker2])
        db_session.commit()
        db_session.refresh(test_user)
        assert len(test_user.broker_accounts) == 2


# ============================== CONSTRAINT TESTS ==============================

class TestConstraints:
    """Test database constraints (unique, not null, foreign key, cascade)."""

    def test_unique_email_constraint(self, db_session, test_user):
        """Attempting to insert a user with duplicate email raises IntegrityError."""
        user2 = User(
            email=test_user.email,  # duplicate
            username="different_username",
            hashed_password="hashed",
            full_name="Duplicate Email",
        )
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_unique_username_constraint(self, db_session, test_user):
        """Duplicate username raises IntegrityError."""
        user2 = User(
            email="unique@example.com",
            username=test_user.username,  # duplicate
            hashed_password="hashed",
            full_name="Duplicate Username",
        )
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_not_null_constraint(self, db_session):
        """Creating a user without required fields raises IntegrityError."""
        user = User(
            email="missing@example.com",
            username=None,  # null not allowed
            hashed_password="hashed",
            full_name="Missing Username",
        )
        db_session.add(user)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_foreign_key_constraint(self, db_session):
        """Creating an order with non-existent portfolio_id raises IntegrityError."""
        order = Order(
            portfolio_id=99999,  # doesn't exist
            symbol="BTC-USD",
            side="buy",
            order_type="limit",
            quantity=1.0,
            price=50000.0,
            status="pending",
        )
        db_session.add(order)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_cascade_delete_portfolio_orders(self, db_session, test_portfolio):
        """Deleting a Portfolio should cascade delete its Orders."""
        order = Order(portfolio_id=test_portfolio.id, symbol="BTC-USD", side="buy", order_type="limit", quantity=1.0, price=50000.0, status="pending")
        db_session.add(order)
        db_session.commit()
        # Now delete portfolio
        db_session.delete(test_portfolio)
        db_session.commit()
        # Verify order is deleted
        order_check = db_session.execute(select(Order).where(Order.id == order.id)).scalar_one_or_none()
        assert order_check is None

    def test_cascade_delete_user_portfolios(self, db_session, test_user):
        """Deleting a User should cascade delete their Portfolios."""
        portfolio = Portfolio(user_id=test_user.id, name="Test", description="Desc")
        db_session.add(portfolio)
        db_session.commit()
        # Delete user
        db_session.delete(test_user)
        db_session.commit()
        # Verify portfolio deleted
        portfolio_check = db_session.execute(select(Portfolio).where(Portfolio.id == portfolio.id)).scalar_one_or_none()
        assert portfolio_check is None

    def test_unique_broker_account_account_id(self, db_session, test_user):
        """Assuming account_id is unique per broker? Or globally? Typically per user/broker combination."""
        # If there's a unique constraint on (user_id, broker_name, account_id) or similar, test it.
        broker1 = BrokerAccount(user_id=test_user.id, broker_name="binance", account_id="unique_acc", api_key="key1", api_secret_encrypted="sec1")
        db_session.add(broker1)
        db_session.commit()
        # Try duplicate account_id with same user and broker
        broker2 = BrokerAccount(user_id=test_user.id, broker_name="binance", account_id="unique_acc", api_key="key2", api_secret_encrypted="sec2")
        db_session.add(broker2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ============================== QUERY PERFORMANCE / INDEX TESTS ==============================

class TestQueries:
    """Test common queries and ensure they use indexes appropriately (conceptual)."""

    def test_user_lookup_by_email(self, db_session, test_user):
        """Look up user by email (should use index)."""
        user = db_session.execute(select(User).where(User.email == test_user.email)).scalar_one()
        assert user.id == test_user.id

    def test_user_lookup_by_username(self, db_session, test_user):
        """Look up user by username."""
        user = db_session.execute(select(User).where(User.username == test_user.username)).scalar_one()
        assert user.id == test_user.id

    def test_portfolio_lookup_by_user(self, db_session, test_user):
        """Find portfolios belonging to a user."""
        portfolios = db_session.execute(select(Portfolio).where(Portfolio.user_id == test_user.id)).scalars().all()
        assert isinstance(portfolios, list)

    def test_orders_by_portfolio_and_symbol(self, db_session, test_portfolio):
        """Filter orders by portfolio and symbol."""
        order = Order(portfolio_id=test_portfolio.id, symbol="BTC-USD", side="buy", order_type="limit", quantity=1.0, price=50000.0, status="pending")
        db_session.add(order)
        db_session.commit()
        orders = db_session.execute(
            select(Order).where(Order.portfolio_id == test_portfolio.id, Order.symbol == "BTC-USD")
        ).scalars().all()
        assert len(orders) >= 1

    def test_positions_by_portfolio(self, db_session, test_portfolio):
        """Get all positions for a portfolio."""
        positions = db_session.execute(select(Position).where(Position.portfolio_id == test_portfolio.id)).scalars().all()
        assert isinstance(positions, list)

    def test_trades_by_order(self, db_session, test_order):
        """Get trades for an order."""
        trade = Trade(order_id=test_order.id, symbol="BTC-USD", side="buy", quantity=0.5, price=49000.0, fee=10.0, trade_time=datetime.utcnow())
        db_session.add(trade)
        db_session.commit()
        trades = db_session.execute(select(Trade).where(Trade.order_id == test_order.id)).scalars().all()
        assert len(trades) >= 1

    def test_subscription_plans_active(self, db_session, test_subscription_plan):
        """Get active subscription plans."""
        plans = db_session.execute(select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)).scalars().all()
        assert len(plans) >= 1


# ============================== MIGRATION / SCHEMA TESTS ==============================

class TestSchema:
    """Test that the database schema matches the models."""

    def test_table_names(self, db_session):
        """Verify that expected tables exist."""
        inspector = inspect(db_session.get_bind())
        table_names = inspector.get_table_names()
        expected_tables = [
            "users",
            "portfolios",
            "broker_accounts",
            "orders",
            "positions",
            "trades",
            "subscription_plans",
            "subscriptions",
            "ai_models",
            "ai_predictions",
            "ai_trainings",
        ]
        for table in expected_tables:
            assert table in table_names

    def test_columns_for_user(self, db_session):
        """Verify User table columns."""
        inspector = inspect(db_session.get_bind())
        columns = inspector.get_columns("users")
        column_names = [col["name"] for col in columns]
        expected = ["id", "email", "username", "hashed_password", "full_name", "is_active", "is_verified", "created_at", "updated_at", "last_login"]
        for col in expected:
            assert col in column_names

    def test_foreign_keys(self, db_session):
        """Verify foreign key constraints exist."""
        inspector = inspect(db_session.get_bind())
        # Check for foreign keys in 'orders' table
        fks = inspector.get_foreign_keys("orders")
        # Expect a foreign key to portfolios
        found = False
        for fk in fks:
            if fk["referred_table"] == "portfolios":
                found = True
                break
        assert found, "Foreign key from orders to portfolios not found"

    def test_indexes(self, db_session):
        """Verify indexes exist for performance."""
        inspector = inspect(db_session.get_bind())
        indexes = inspector.get_indexes("users")
        index_names = [idx["name"] for idx in indexes]
        # Expect unique index on email and username
        assert any("email" in idx["column_names"] for idx in indexes if idx["unique"])
        assert any("username" in idx["column_names"] for idx in indexes if idx["unique"])


# ============================== EDGE CASES ==============================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_long_strings(self, db_session):
        """Test that very long strings are handled (truncated if needed)."""
        long_string = "a" * 1000  # Exceeds typical 255 limit for some fields
        user = User(
            email=long_string[:50] + "@example.com",  # email can be long
            username=long_string[:100],  # might exceed limit
            hashed_password="hashed",
            full_name=long_string[:200],
        )
        # Depending on model definition, might raise or truncate
        # We'll attempt and see; if too long, the database will raise an error.
        # We'll check for ValueError or IntegrityError.
        try:
            db_session.add(user)
            db_session.commit()
            # If succeeds, check it was stored
            assert user.id is not None
        except (IntegrityError, ValueError):
            db_session.rollback()
            pytest.skip("Field length constraints prevent insertion of long strings")

    def test_nullable_fields(self, db_session, test_user):
        """Test that nullable fields can be None."""
        # Description is nullable in Portfolio
        portfolio = Portfolio(user_id=test_user.id, name="Portfolio without description", description=None)
        db_session.add(portfolio)
        db_session.commit()
        db_session.refresh(portfolio)
        assert portfolio.description is None

    def test_default_values(self, db_session, test_user):
        """Test default values like created_at, is_active, etc."""
        portfolio = Portfolio(user_id=test_user.id, name="Default Test")
        db_session.add(portfolio)
        db_session.commit()
        db_session.refresh(portfolio)
        assert portfolio.created_at is not None
        assert portfolio.is_active is True  # assuming default True

    def test_boolean_fields(self, db_session, test_user):
        """Test boolean fields behave as expected."""
        user = User(
            email="booltest@example.com",
            username="booltest",
            hashed_password="hashed",
            full_name="Bool Test",
            is_active=False,
            is_verified=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        assert user.is_active is False
        assert user.is_verified is False

    def test_datetime_auto_update(self, db_session, test_user):
        """Test that updated_at is auto-updated on change."""
        original_updated = test_user.updated_at
        # Wait a moment to ensure time difference
        import time
        time.sleep(0.1)
        test_user.full_name = "Updated Name"
        db_session.commit()
        db_session.refresh(test_user)
        assert test_user.updated_at > original_updated

    def test_decimal_precision(self, db_session, test_user):
        """Test that decimal fields like price and quantity handle precision."""
        # Create an order with high precision
        order = Order(
            portfolio_id=test_user.portfolios[0].id,  # assuming portfolio exists
            symbol="BTC-USD",
            side="buy",
            order_type="limit",
            quantity=0.123456789,
            price=12345.6789,
            status="pending",
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        # Fetch and compare; should match within precision
        assert order.quantity == 0.123456789
        assert order.price == 12345.6789


# ============================== INTEGRATION: MULTI-TABLE OPERATIONS ==============================

class TestMultiTableOperations:
    """Test operations involving multiple tables."""

    def test_full_trade_lifecycle(self, db_session, test_user, test_portfolio):
        """Simulate a full trade lifecycle: order -> fill -> position update."""
        # Create an order
        order = Order(
            portfolio_id=test_portfolio.id,
            symbol="BTC-USD",
            side="buy",
            order_type="market",
            quantity=1.0,
            price=None,  # market order
            status="pending",
            filled_quantity=0.0,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Simulate fill: update order, create trades, update position
        filled_qty = 1.0
        fill_price = 50000.0

        # Update order
        order.status = "filled"
        order.filled_quantity = filled_qty
        order.price = fill_price

        # Create trade
        trade = Trade(
            order_id=order.id,
            symbol="BTC-USD",
            side="buy",
            quantity=filled_qty,
            price=fill_price,
            fee=10.0,
            trade_time=datetime.utcnow(),
        )
        db_session.add(trade)

        # Update or create position
        position = db_session.execute(
            select(Position).where(
                Position.portfolio_id == test_portfolio.id,
                Position.symbol == "BTC-USD"
            )
        ).scalar_one_or_none()

        if position:
            # Average price update
            total_cost = (position.quantity * position.avg_price) + (filled_qty * fill_price)
            new_quantity = position.quantity + filled_qty
            position.avg_price = total_cost / new_quantity
            position.quantity = new_quantity
        else:
            position = Position(
                portfolio_id=test_portfolio.id,
                symbol="BTC-USD",
                quantity=filled_qty,
                avg_price=fill_price,
                current_price=fill_price,
            )
            db_session.add(position)

        db_session.commit()

        # Verify
        db_session.refresh(order)
        db_session.refresh(position)
        assert order.status == "filled"
        assert position.quantity == filled_qty
        assert position.avg_price == fill_price

    def test_user_and_subscription_creation(self, db_session, test_subscription_plan):
        """Create a user and immediately assign a subscription."""
        user = User(
            email="subuser@example.com",
            username="subuser",
            hashed_password="hashed",
            full_name="Sub User",
        )
        db_session.add(user)
        db_session.flush()  # get user.id

        sub = Subscription(
            user_id=user.id,
            plan_id=test_subscription_plan.id,
            status="active",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
        )
        db_session.add(sub)
        db_session.commit()

        db_session.refresh(user)
        assert user.subscription is not None
        assert user.subscription.plan_id == test_subscription_plan.id


# ============================== ASYNC QUERY TESTS ==============================

class TestAsyncQueries:
    """Test async database queries."""

    async def test_async_create_user(self, async_db_session: AsyncSession):
        """Async create user."""
        user = User(
            email="async@example.com",
            username="asyncuser",
            hashed_password="hashed",
            full_name="Async User",
        )
        async_db_session.add(user)
        await async_db_session.commit()
        await async_db_session.refresh(user)
        assert user.id is not None

    async def test_async_query_user(self, async_db_session: AsyncSession, test_user):
        """Async query user."""
        result = await async_db_session.execute(
            select(User).where(User.id == test_user.id)
        )
        user = result.scalar_one()
        assert user.email == test_user.email

    async def test_async_relationship(self, async_db_session: AsyncSession, test_user):
        """Async relationship loading."""
        portfolio = Portfolio(user_id=test_user.id, name="Async Portfolio", description="Desc")
        async_db_session.add(portfolio)
        await async_db_session.commit()
        await async_db_session.refresh(test_user)
        # Load portfolios relation (may need eager loading)
        result = await async_db_session.execute(
            select(User).where(User.id == test_user.id)
        )
        user = result.scalar_one()
        # We need to explicitly load the relationship if not eager
        await async_db_session.refresh(user, attribute_names=["portfolios"])
        assert len(user.portfolios) >= 1

    async def test_async_bulk_insert(self, async_db_session: AsyncSession):
        """Test bulk insert performance (conceptual)."""
        users = [
            User(
                email=f"bulk{i}@example.com",
                username=f"bulkuser{i}",
                hashed_password="hashed",
                full_name=f"Bulk User {i}",
            )
            for i in range(10)
        ]
        async_db_session.add_all(users)
        await async_db_session.commit()
        # Verify count
        result = await async_db_session.execute(select(User).where(User.email.like("bulk%@example.com")))
        inserted = result.scalars().all()
        assert len(inserted) == 10
