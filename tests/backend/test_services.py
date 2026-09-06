# tests/backend/test_services.py
"""
Service Layer Tests for the NEXUS AI Trading System.

This module contains comprehensive tests for all service classes:
- PortfolioService: CRUD operations, position management
- TradingService: Order placement, cancellation, execution
- BrokerService: Broker account management, external API calls
- AIService: Prediction generation, model training, registry
- RiskService: Position sizing, risk checks, portfolio risk metrics
- SubscriptionService: Plan management, user subscription handling

All tests use mocking to avoid external API calls and database side effects.
Fixtures are imported from conftest.py and patching is applied where needed.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.portfolio import Portfolio
from backend.models.order import Order
from backend.models.position import Position
from backend.models.broker_account import BrokerAccount
from backend.models.user import User
from backend.models.subscription import Subscription, SubscriptionPlan
from backend.services.portfolio_service import PortfolioService
from backend.services.trading_service import TradingService
from backend.services.broker_service import BrokerService
from backend.services.ai_service import AIService
from backend.services.risk_service import RiskService
from backend.services.subscription_service import SubscriptionService

pytest_plugins = ["tests.backend.conftest"]


# ============================== PORTFOLIO SERVICE TESTS ==============================

class TestPortfolioService:
    """Test the PortfolioService class."""

    @pytest.fixture
    def portfolio_service(self, async_db_session: AsyncSession):
        """Return a PortfolioService instance with real session."""
        return PortfolioService(db=async_db_session)

    async def test_create_portfolio(
        self,
        portfolio_service: PortfolioService,
        async_db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating a new portfolio."""
        name = "Test Portfolio"
        description = "Test Description"
        portfolio = await portfolio_service.create_portfolio(
            user_id=test_user.id,
            name=name,
            description=description,
        )
        assert portfolio.id is not None
        assert portfolio.name == name
        assert portfolio.description == description
        assert portfolio.user_id == test_user.id
        assert portfolio.is_active is True

    async def test_get_portfolio(
        self,
        portfolio_service: PortfolioService,
        test_portfolio: Portfolio,
    ):
        """Test retrieving a portfolio by ID."""
        portfolio = await portfolio_service.get_portfolio(test_portfolio.id)
        assert portfolio.id == test_portfolio.id
        assert portfolio.name == test_portfolio.name

    async def test_get_portfolio_not_found(
        self,
        portfolio_service: PortfolioService,
    ):
        """Test that retrieving a non-existent portfolio raises an exception."""
        with pytest.raises(Exception) as exc:
            await portfolio_service.get_portfolio(99999)
        assert "not found" in str(exc.value).lower()

    async def test_list_portfolios(
        self,
        portfolio_service: PortfolioService,
        test_user: User,
        async_db_session: AsyncSession,
    ):
        """Test listing portfolios for a user."""
        # Create multiple portfolios
        for i in range(3):
            await portfolio_service.create_portfolio(
                user_id=test_user.id,
                name=f"Portfolio {i}",
                description=f"Desc {i}",
            )
        portfolios = await portfolio_service.list_portfolios(user_id=test_user.id)
        assert len(portfolios) >= 3
        # Verify all belong to the user
        for p in portfolios:
            assert p.user_id == test_user.id

    async def test_update_portfolio(
        self,
        portfolio_service: PortfolioService,
        test_portfolio: Portfolio,
    ):
        """Test updating portfolio details."""
        new_name = "Updated Name"
        new_desc = "Updated Description"
        updated = await portfolio_service.update_portfolio(
            portfolio_id=test_portfolio.id,
            name=new_name,
            description=new_desc,
        )
        assert updated.name == new_name
        assert updated.description == new_desc

    async def test_delete_portfolio(
        self,
        portfolio_service: PortfolioService,
        test_portfolio: Portfolio,
    ):
        """Test deleting a portfolio."""
        await portfolio_service.delete_portfolio(test_portfolio.id)
        with pytest.raises(Exception):
            await portfolio_service.get_portfolio(test_portfolio.id)

    async def test_add_position(
        self,
        portfolio_service: PortfolioService,
        test_portfolio: Portfolio,
    ):
        """Test adding a position to a portfolio."""
        position = await portfolio_service.add_position(
            portfolio_id=test_portfolio.id,
            symbol="BTC-USD",
            quantity=0.5,
            avg_price=50000.0,
        )
        assert position.id is not None
        assert position.symbol == "BTC-USD"
        assert position.quantity == 0.5
        assert position.avg_price == 50000.0
        assert position.portfolio_id == test_portfolio.id

    async def test_remove_position(
        self,
        portfolio_service: PortfolioService,
        test_position: Position,
    ):
        """Test removing a position."""
        await portfolio_service.remove_position(test_position.id)
        # Should no longer exist
        positions = await portfolio_service.list_positions(portfolio_id=test_position.portfolio_id)
        assert test_position.id not in [p.id for p in positions]


# ============================== TRADING SERVICE TESTS ==============================

class TestTradingService:
    """Test the TradingService class."""

    @pytest.fixture
    def trading_service(self, async_db_session: AsyncSession):
        """Return a TradingService instance."""
        return TradingService(db=async_db_session)

    @pytest.fixture
    def mock_broker(self):
        """Mock the broker client."""
        mock = AsyncMock()
        mock.place_order = AsyncMock(return_value={"id": "broker_ord_123", "status": "filled"})
        mock.get_order = AsyncMock(return_value={"id": "broker_ord_123", "status": "filled", "filled_qty": 1.0})
        mock.cancel_order = AsyncMock(return_value={"status": "cancelled"})
        return mock

    async def test_place_market_order(
        self,
        trading_service: TradingService,
        test_portfolio: Portfolio,
        mock_broker,
        async_db_session: AsyncSession,
    ):
        """Test placing a market order."""
        with patch.object(trading_service, "_get_broker", return_value=mock_broker):
            order = await trading_service.place_order(
                portfolio_id=test_portfolio.id,
                symbol="BTC-USD",
                side="buy",
                order_type="market",
                quantity=1.0,
                price=None,
            )
            assert order.id is not None
            assert order.symbol == "BTC-USD"
            assert order.side == "buy"
            assert order.order_type == "market"
            assert order.quantity == 1.0
            assert order.status == "filled"
            assert order.broker_order_id == "broker_ord_123"
            # Verify position was created/updated
            positions = await trading_service._portfolio_service.list_positions(test_portfolio.id)
            pos = next((p for p in positions if p.symbol == "BTC-USD"), None)
            assert pos is not None
            # Filled at the price from the broker (we mocked it)
            # We should check that position exists; exact price may be from mock.

    async def test_place_limit_order(
        self,
        trading_service: TradingService,
        test_portfolio: Portfolio,
        mock_broker,
    ):
        """Test placing a limit order."""
        with patch.object(trading_service, "_get_broker", return_value=mock_broker):
            # Mock broker to return pending status (limit order not filled immediately)
            mock_broker.place_order.return_value = {"id": "broker_ord_456", "status": "pending"}
            order = await trading_service.place_order(
                portfolio_id=test_portfolio.id,
                symbol="ETH-USD",
                side="sell",
                order_type="limit",
                quantity=2.0,
                price=3500.0,
            )
            assert order.id is not None
            assert order.order_type == "limit"
            assert order.price == 3500.0
            assert order.status == "pending"
            assert order.broker_order_id == "broker_ord_456"

    async def test_cancel_order(
        self,
        trading_service: TradingService,
        test_order: Order,
        mock_broker,
    ):
        """Test cancelling an order."""
        with patch.object(trading_service, "_get_broker", return_value=mock_broker):
            # Set order to pending to allow cancellation
            test_order.status = "pending"
            await trading_service.db.commit()
            cancelled = await trading_service.cancel_order(test_order.id)
            assert cancelled.status == "cancelled"
            mock_broker.cancel_order.assert_called_once_with(test_order.broker_order_id)

    async def test_get_order_status(
        self,
        trading_service: TradingService,
        test_order: Order,
        mock_broker,
    ):
        """Test fetching order status from broker."""
        with patch.object(trading_service, "_get_broker", return_value=mock_broker):
            status = await trading_service.get_order_status(test_order.id)
            assert status["id"] == "broker_ord_123"
            assert status["status"] == "filled"
            mock_broker.get_order.assert_called_once_with(test_order.broker_order_id)

    async def test_place_order_insufficient_balance(
        self,
        trading_service: TradingService,
        test_portfolio: Portfolio,
    ):
        """Test that placing an order with insufficient balance raises an error."""
        # Mock broker to raise insufficient balance
        mock_broker = AsyncMock()
        mock_broker.place_order.side_effect = Exception("Insufficient balance")
        with patch.object(trading_service, "_get_broker", return_value=mock_broker):
            with pytest.raises(Exception) as exc:
                await trading_service.place_order(
                    portfolio_id=test_portfolio.id,
                    symbol="BTC-USD",
                    side="buy",
                    order_type="market",
                    quantity=1000.0,
                )
            assert "balance" in str(exc.value).lower()


# ============================== BROKER SERVICE TESTS ==============================

class TestBrokerService:
    """Test the BrokerService class."""

    @pytest.fixture
    def broker_service(self, async_db_session: AsyncSession):
        """Return a BrokerService instance."""
        return BrokerService(db=async_db_session)

    async def test_connect_account(
        self,
        broker_service: BrokerService,
        test_user: User,
    ):
        """Test connecting a new broker account."""
        account = await broker_service.connect_account(
            user_id=test_user.id,
            broker_name="binance",
            api_key="test_api_key",
            api_secret="test_api_secret",
            label="My Binance",
        )
        assert account.id is not None
        assert account.broker_name == "binance"
        assert account.user_id == test_user.id
        assert account.label == "My Binance"
        # Sensitive data should be encrypted
        assert account.api_key != "test_api_key"  # Should be encrypted
        assert account.api_secret_encrypted is not None

    async def test_get_account(
        self,
        broker_service: BrokerService,
        test_broker_account: BrokerAccount,
    ):
        """Test retrieving a broker account."""
        account = await broker_service.get_account(test_broker_account.id)
        assert account.id == test_broker_account.id
        assert account.broker_name == test_broker_account.broker_name

    async def test_get_accounts_for_user(
        self,
        broker_service: BrokerService,
        test_user: User,
        test_broker_account: BrokerAccount,
    ):
        """Test listing accounts for a user."""
        accounts = await broker_service.get_accounts_for_user(test_user.id)
        assert len(accounts) >= 1
        assert any(a.id == test_broker_account.id for a in accounts)

    async def test_delete_account(
        self,
        broker_service: BrokerService,
        test_broker_account: BrokerAccount,
    ):
        """Test deleting a broker account."""
        await broker_service.delete_account(test_broker_account.id)
        with pytest.raises(Exception):
            await broker_service.get_account(test_broker_account.id)

    async def test_get_balance(
        self,
        broker_service: BrokerService,
        test_broker_account: BrokerAccount,
    ):
        """Test fetching balance from broker."""
        mock_broker = AsyncMock()
        mock_broker.get_balance = AsyncMock(return_value={"total": 10000.0, "available": 9500.0})
        with patch.object(broker_service, "_get_broker_client", return_value=mock_broker):
            balance = await broker_service.get_balance(test_broker_account.id)
            assert balance["total"] == 10000.0
            assert balance["available"] == 9500.0
            mock_broker.get_balance.assert_called_once()

    async def test_get_positions(
        self,
        broker_service: BrokerService,
        test_broker_account: BrokerAccount,
    ):
        """Test fetching positions from broker."""
        mock_broker = AsyncMock()
        mock_broker.get_positions = AsyncMock(return_value=[
            {"symbol": "BTC-USD", "quantity": 0.5, "avg_price": 50000.0, "current_price": 51000.0}
        ])
        with patch.object(broker_service, "_get_broker_client", return_value=mock_broker):
            positions = await broker_service.get_positions(test_broker_account.id)
            assert len(positions) == 1
            assert positions[0]["symbol"] == "BTC-USD"
            mock_broker.get_positions.assert_called_once()


# ============================== AI SERVICE TESTS ==============================

class TestAIService:
    """Test the AIService class."""

    @pytest.fixture
    def ai_service(self, async_db_session: AsyncSession):
        """Return an AIService instance."""
        return AIService(db=async_db_session)

    async def test_get_prediction(
        self,
        ai_service: AIService,
        test_user: User,
    ):
        """Test getting a prediction for a symbol."""
        # Mock the model inference
        mock_model = AsyncMock()
        mock_model.predict = AsyncMock(return_value={"price": 51000.0, "confidence": 0.85})
        with patch.object(ai_service, "_load_model", return_value=mock_model):
            prediction = await ai_service.get_prediction(
                user_id=test_user.id,
                symbol="BTC-USD",
                timeframe="1h",
            )
            assert prediction["symbol"] == "BTC-USD"
            assert prediction["predicted_price"] == 51000.0
            assert prediction["confidence"] == 0.85
            # Check that a record was saved in DB (AIPrediction)
            # We can query the database to verify, but we trust the service.
            # For testing, we might want to check that the db record was created.
            # We'll just ensure the function returns a dict.

    async def test_get_prediction_with_cache(
        self,
        ai_service: AIService,
        test_user: User,
    ):
        """Test that predictions are cached to avoid repeated inference."""
        # First call: model invoked
        mock_model = AsyncMock()
        mock_model.predict = AsyncMock(return_value={"price": 51000.0, "confidence": 0.85})
        with patch.object(ai_service, "_load_model", return_value=mock_model):
            pred1 = await ai_service.get_prediction(
                user_id=test_user.id,
                symbol="BTC-USD",
                timeframe="1h",
            )
            # Second call: should use cache
            pred2 = await ai_service.get_prediction(
                user_id=test_user.id,
                symbol="BTC-USD",
                timeframe="1h",
            )
            assert pred1 == pred2
            assert mock_model.predict.call_count == 1

    async def test_train_model(
        self,
        ai_service: AIService,
        test_user: User,
    ):
        """Test triggering model training."""
        # Mock the training process
        mock_trainer = AsyncMock()
        mock_trainer.train = AsyncMock(return_value={"status": "completed", "metrics": {"accuracy": 0.92}})
        with patch.object(ai_service, "_get_trainer", return_value=mock_trainer):
            result = await ai_service.train_model(
                user_id=test_user.id,
                model_name="lstm",
                symbols=["BTC-USD", "ETH-USD"],
                timeframe="1h",
            )
            assert result["status"] == "completed"
            assert "metrics" in result
            # Check that an AITraining record was created
            # We could query db, but we trust the implementation.

    async def test_list_models(
        self,
        ai_service: AIService,
        async_db_session: AsyncSession,
    ):
        """Test listing available trained models."""
        # Insert a few models into DB (or use fixture)
        from backend.models.ai_model import AIModel
        model1 = AIModel(model_name="lstm_v1", model_type="lstm", version="1.0", framework="pytorch", is_active=True)
        model2 = AIModel(model_name="xgboost_v1", model_type="xgboost", version="1.0", framework="sklearn", is_active=True)
        async_db_session.add_all([model1, model2])
        await async_db_session.commit()

        models = await ai_service.list_models()
        assert len(models) >= 2
        assert any(m["name"] == "lstm_v1" for m in models)
        assert any(m["name"] == "xgboost_v1" for m in models)


# ============================== RISK SERVICE TESTS ==============================

class TestRiskService:
    """Test the RiskService class."""

    @pytest.fixture
    def risk_service(self, async_db_session: AsyncSession):
        """Return a RiskService instance."""
        return RiskService(db=async_db_session)

    async def test_check_position_risk_allowed(
        self,
        risk_service: RiskService,
        test_portfolio: Portfolio,
    ):
        """Test risk check for a new position within limits."""
        # Set risk limits (e.g., max position size = $100,000)
        # We'll mock the portfolio's risk settings or just use defaults.
        # For this test, we'll assume default limits are high.
        # We'll also mock the current portfolio value.
        with patch.object(risk_service, "_get_portfolio_value", return_value=100000.0):
            result = await risk_service.check_position_risk(
                portfolio_id=test_portfolio.id,
                symbol="BTC-USD",
                side="buy",
                quantity=0.5,
                price=50000.0,
            )
            assert result["allowed"] is True
            assert "reason" not in result or result["reason"] == "OK"

    async def test_check_position_risk_exceeds_limit(
        self,
        risk_service: RiskService,
        test_portfolio: Portfolio,
    ):
        """Test risk check fails when position size exceeds limits."""
        with patch.object(risk_service, "_get_portfolio_value", return_value=100000.0):
            result = await risk_service.check_position_risk(
                portfolio_id=test_portfolio.id,
                symbol="BTC-USD",
                side="buy",
                quantity=10.0,  # $500,000 -> exceeds typical limit
                price=50000.0,
            )
            assert result["allowed"] is False
            assert "limit" in result["reason"].lower()

    async def test_calculate_position_size(
        self,
        risk_service: RiskService,
        test_portfolio: Portfolio,
    ):
        """Test position sizing based on risk percentage."""
        # Assume risk per trade = 1% of portfolio, stop loss = 5%
        # Portfolio value = 100,000
        # Position size = (100,000 * 0.01) / (100,000 * 0.05) * 100,000? Actually formula: size = (risk_amount) / (entry - stop)
        # We'll simplify: size = (portfolio_value * risk_percentage) / (stop_loss_percentage)
        # For BTC at 50,000, stop at 47,500 (5% drop), risk amount = 1,000 (1% of 100k)
        # size = 1000 / (50000 - 47500) * 50000? Actually size in units = risk_amount / (entry - stop)
        # = 1000 / 2500 = 0.4 BTC
        with patch.object(risk_service, "_get_portfolio_value", return_value=100000.0):
            size = await risk_service.calculate_position_size(
                portfolio_id=test_portfolio.id,
                symbol="BTC-USD",
                entry_price=50000.0,
                stop_loss_price=47500.0,
                risk_percentage=0.01,  # 1%
            )
            # Allow some rounding tolerance
            assert abs(size - 0.4) < 0.01

    async def test_get_portfolio_risk_metrics(
        self,
        risk_service: RiskService,
        test_portfolio: Portfolio,
        test_position: Position,
    ):
        """Test calculating risk metrics for a portfolio."""
        # Mock the positions and current prices
        # We'll rely on test_position fixture (BTC-USD at 50,000)
        # Add another position for diversification
        from backend.models.position import Position
        pos2 = Position(
            portfolio_id=test_portfolio.id,
            symbol="ETH-USD",
            quantity=2.0,
            avg_price=3000.0,
            current_price=3100.0,
        )
        test_portfolio.positions.append(pos2)
        await risk_service.db.commit()

        metrics = await risk_service.get_portfolio_risk_metrics(test_portfolio.id)
        assert "total_value" in metrics
        assert "var_95" in metrics
        assert "var_99" in metrics
        assert "sharpe_ratio" in metrics or "sharpe" in metrics
        # Check that values are reasonable
        assert metrics["total_value"] > 0
        assert metrics["var_95"] <= 0  # VaR is negative or zero


# ============================== SUBSCRIPTION SERVICE TESTS ==============================

class TestSubscriptionService:
    """Test the SubscriptionService class."""

    @pytest.fixture
    def subscription_service(self, async_db_session: AsyncSession):
        """Return a SubscriptionService instance."""
        return SubscriptionService(db=async_db_session)

    async def test_create_subscription_plan(
        self,
        subscription_service: SubscriptionService,
    ):
        """Test creating a new subscription plan."""
        plan_data = {
            "name": "Premium Plan",
            "description": "Premium features",
            "price_monthly": 199.99,
            "price_yearly": 1999.99,
            "features": {"ai_predictions": True, "auto_trading": True, "advanced_risk": True},
            "max_positions": 100,
            "max_portfolios": 10,
            "is_active": True,
        }
        plan = await subscription_service.create_plan(plan_data)
        assert plan.id is not None
        assert plan.name == "Premium Plan"
        assert plan.price_monthly == 199.99

    async def test_get_active_plans(
        self,
        subscription_service: SubscriptionService,
        test_subscription_plan: SubscriptionPlan,
    ):
        """Test listing active plans."""
        plans = await subscription_service.get_active_plans()
        assert len(plans) >= 1
        assert any(p.id == test_subscription_plan.id for p in plans)

    async def test_subscribe_user(
        self,
        subscription_service: SubscriptionService,
        test_user: User,
        test_subscription_plan: SubscriptionPlan,
    ):
        """Test subscribing a user to a plan."""
        subscription = await subscription_service.subscribe_user(
            user_id=test_user.id,
            plan_id=test_subscription_plan.id,
        )
        assert subscription.id is not None
        assert subscription.user_id == test_user.id
        assert subscription.plan_id == test_subscription_plan.id
        assert subscription.status == "active"
        assert subscription.start_date <= datetime.utcnow()
        assert subscription.end_date >= subscription.start_date

    async def test_cancel_subscription(
        self,
        subscription_service: SubscriptionService,
        test_subscription: Subscription,
    ):
        """Test cancelling a subscription."""
        cancelled = await subscription_service.cancel_subscription(test_subscription.id)
        assert cancelled.status == "cancelled"
        # End date may be updated or just status changed.

    async def test_check_subscription_active(
        self,
        subscription_service: SubscriptionService,
        test_user: User,
        test_subscription: Subscription,
    ):
        """Test checking if a user has an active subscription."""
        # Active subscription exists
        is_active = await subscription_service.is_active(test_user.id)
        assert is_active is True
        # Cancel it and check again
        await subscription_service.cancel_subscription(test_subscription.id)
        is_active = await subscription_service.is_active(test_user.id)
        assert is_active is False


# ============================== INTEGRATION: END-TO-END SERVICE FLOW ==============================

class TestServiceIntegration:
    """Test end-to-end flows involving multiple services."""

    async def test_trade_flow_with_risk_check(
        self,
        async_db_session: AsyncSession,
        test_portfolio: Portfolio,
        test_user: User,
        test_broker_account: BrokerAccount,
    ):
        """Simulate a full trade: risk check -> place order -> update portfolio."""
        # Initialize services
        portfolio_service = PortfolioService(db=async_db_session)
        risk_service = RiskService(db=async_db_session)
        trading_service = TradingService(db=async_db_session)
        broker_service = BrokerService(db=async_db_session)

        # Mock broker
        mock_broker = AsyncMock()
        mock_broker.place_order = AsyncMock(return_value={"id": "broker_ord_999", "status": "filled", "filled_qty": 0.5, "price": 50000.0})
        mock_broker.get_balance = AsyncMock(return_value={"total": 100000.0, "available": 95000.0})

        with patch.object(trading_service, "_get_broker", return_value=mock_broker):
            # Risk check
            risk_result = await risk_service.check_position_risk(
                portfolio_id=test_portfolio.id,
                symbol="BTC-USD",
                side="buy",
                quantity=0.5,
                price=50000.0,
            )
            assert risk_result["allowed"] is True

            # Place order
            order = await trading_service.place_order(
                portfolio_id=test_portfolio.id,
                symbol="BTC-USD",
                side="buy",
                order_type="market",
                quantity=0.5,
            )
            assert order.status == "filled"

            # Check position was created/updated
            positions = await portfolio_service.list_positions(test_portfolio.id)
            pos = next((p for p in positions if p.symbol == "BTC-USD"), None)
            assert pos is not None
            assert pos.quantity == 0.5

    async def test_subscription_limits(
        self,
        async_db_session: AsyncSession,
        test_user: User,
        test_subscription_plan: SubscriptionPlan,
    ):
        """Test that subscription limits (max portfolios) are enforced."""
        subscription_service = SubscriptionService(db=async_db_session)
        portfolio_service = PortfolioService(db=async_db_session)

        # Subscribe user with plan that allows max 1 portfolio
        # We'll modify the plan's max_portfolios to 1
        test_subscription_plan.max_portfolios = 1
        await async_db_session.commit()

        await subscription_service.subscribe_user(
            user_id=test_user.id,
            plan_id=test_subscription_plan.id,
        )

        # Create first portfolio (should succeed)
        await portfolio_service.create_portfolio(
            user_id=test_user.id,
            name="Portfolio 1",
            description="First",
        )

        # Create second portfolio (should fail due to limit)
        with pytest.raises(Exception) as exc:
            await portfolio_service.create_portfolio(
                user_id=test_user.id,
                name="Portfolio 2",
                description="Second",
            )
        assert "limit" in str(exc.value).lower() or "subscription" in str(exc.value).lower()
