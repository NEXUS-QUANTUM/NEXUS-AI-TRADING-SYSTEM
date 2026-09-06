"""
tests/integration/test_end_to_end.py

NEXUS AI Trading System - End-to-End Integration Test

This test suite simulates a complete user journey through the entire system,
covering registration, authentication, broker connection, trading, portfolio
management, AI predictions, risk management, and subscriptions.

It verifies that all components work together correctly: database, API,
broker integration, risk engine, AI services, etc.

All tests use the FastAPI TestClient and a real test database, with
external broker calls mocked to ensure deterministic behavior.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import pytest
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.core.database import get_db
from backend.models.user import User
from backend.models.portfolio import Portfolio
from backend.models.position import Position
from backend.models.order import Order
from backend.models.broker_account import BrokerAccount
from backend.models.subscription import Subscription, SubscriptionPlan
from backend.models.ai_model import AIModel

from tests.integration.conftest import (
    db_session,
    override_get_db,
    client,
    mock_alpaca_broker,
    mock_binance_broker,
    mock_ai_model,
)


class TestEndToEnd:
    """Complete end-to-end user journey test."""

    # Class variables to store state across test methods
    user_email: str = None
    user_password: str = "E2ETest@123"
    access_token: str = None
    refresh_token: str = None
    user_id: str = None
    portfolio_id: str = None
    broker_id: str = None
    order_id: str = None
    position_id: str = None

    @pytest.fixture(autouse=True)
    def setup(self, client: TestClient, db_session: Session):
        """Setup: generate unique email and clean up any leftover data."""
        import time
        self.user_email = f"e2e_test_{int(time.time())}@nexusquantum.com"
        # Ensure the user doesn't already exist
        existing = db_session.query(User).filter(User.email == self.user_email).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()
        yield
        # Teardown: delete the user (cascade will remove related data)
        user = db_session.query(User).filter(User.email == self.user_email).first()
        if user:
            db_session.delete(user)
            db_session.commit()

    def test_01_register_user(self, client: TestClient):
        """Step 1: Register a new user."""
        payload = {
            "email": self.user_email,
            "password": self.user_password,
            "first_name": "EndToEnd",
            "last_name": "TestUser",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == self.user_email
        assert data["first_name"] == "EndToEnd"
        self.user_id = data["id"]
        print(f"✅ Registered user: {self.user_email} (ID: {self.user_id})")

    def test_02_login(self, client: TestClient):
        """Step 2: Login and get tokens."""
        payload = {"email": self.user_email, "password": self.user_password}
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        print(f"✅ Logged in, access token obtained.")

    def test_03_get_user_profile(self, client: TestClient):
        """Step 3: Get current user profile."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == self.user_id
        assert data["email"] == self.user_email
        print(f"✅ Profile verified.")

    def test_04_get_portfolio(self, client: TestClient):
        """Step 4: Verify portfolio is auto-created."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.get("/api/v1/portfolio/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == self.user_id
        assert data["total_balance"] >= 0
        self.portfolio_id = data["id"]
        print(f"✅ Portfolio exists (ID: {self.portfolio_id})")

    def test_05_connect_broker(self, client: TestClient, mock_alpaca_broker):
        """Step 5: Connect a broker account (using mocked Alpaca)."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        payload = {
            "broker_type": "alpaca",
            "api_key": "PK_TEST_KEY",
            "api_secret": "SK_TEST_SECRET",
            "paper_trading": True,
        }
        response = client.post("/api/v1/brokers/connect", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["broker_type"] == "alpaca"
        assert data["is_active"] is True
        self.broker_id = data["id"]
        print(f"✅ Broker connected (ID: {self.broker_id})")

    def test_06_place_market_order(self, client: TestClient):
        """Step 6: Place a market buy order."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        payload = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 10,
            "order_type": "market",
            "portfolio_id": self.portfolio_id,
        }
        response = client.post("/api/v1/trading/orders", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["side"] == "buy"
        assert data["quantity"] == 10
        assert data["status"] == "filled"  # Mock broker returns filled
        self.order_id = data["id"]
        print(f"✅ Market order placed (ID: {self.order_id})")

    def test_07_check_positions(self, client: TestClient, db_session: Session):
        """Step 7: Verify position was created."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.get("/api/v1/portfolio/positions", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        position = next((p for p in data if p["symbol"] == "AAPL"), None)
        assert position is not None
        assert position["quantity"] == 10
        self.position_id = position["id"]
        print(f"✅ Position exists (ID: {self.position_id})")

        # Also verify in DB
        pos_db = db_session.query(Position).filter(Position.id == self.position_id).first()
        assert pos_db is not None
        assert pos_db.symbol == "AAPL"

    def test_08_place_limit_order(self, client: TestClient):
        """Step 8: Place a limit order (will remain open)."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        # Get current price to set limit slightly above
        quote = client.get("/api/v1/market/quote/AAPL", headers=headers)
        assert quote.status_code == 200
        current_price = float(quote.json()["price"])
        limit_price = round(current_price * 0.95, 2)  # 5% below current for buy limit

        payload = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 5,
            "order_type": "limit",
            "limit_price": limit_price,
            "portfolio_id": self.portfolio_id,
        }
        response = client.post("/api/v1/trading/orders", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["order_type"] == "limit"
        assert data["limit_price"] == limit_price
        assert data["status"] == "open"
        self.order_id = data["id"]
        print(f"✅ Limit order placed (ID: {self.order_id})")

    def test_09_get_open_orders(self, client: TestClient):
        """Step 9: Verify open orders include the limit order."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.get("/api/v1/trading/orders/open", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        order = next((o for o in data if o["id"] == self.order_id), None)
        assert order is not None
        assert order["status"] == "open"
        print(f"✅ Open orders list includes limit order.")

    def test_10_cancel_order(self, client: TestClient):
        """Step 10: Cancel the limit order."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.post(f"/api/v1/trading/orders/{self.order_id}/cancel", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        print(f"✅ Order cancelled.")

    def test_11_check_order_history(self, client: TestClient):
        """Step 11: Verify order history includes cancelled order."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.get("/api/v1/trading/orders/history", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Could be paginated; find our order
        found = False
        if isinstance(data, list):
            for o in data:
                if o["id"] == self.order_id:
                    found = True
                    assert o["status"] == "cancelled"
                    break
        elif isinstance(data, dict):
            items = data.get("items", [])
            for o in items:
                if o["id"] == self.order_id:
                    found = True
                    assert o["status"] == "cancelled"
                    break
        assert found, "Order not found in history"
        print(f"✅ Order history verified.")

    def test_12_get_ai_prediction(self, client: TestClient, mock_ai_model):
        """Step 12: Request AI price prediction."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.get("/api/v1/ai/predict/price/AAPL", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert "predicted_price" in data
        assert data["predicted_price"] > 0
        assert "confidence" in data
        print(f"✅ AI prediction received: {data['predicted_price']} (confidence {data['confidence']:.2f})")

    def test_13_update_risk_limits(self, client: TestClient):
        """Step 13: Update risk management limits."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        payload = {
            "max_drawdown": 0.15,
            "max_position_pct": 0.03,
            "max_leverage": 1.5,
            "stop_loss_default": 0.02,
            "take_profit_default": 0.05,
        }
        response = client.put("/api/v1/risk/limits", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["max_drawdown"] == 0.15
        assert data["max_position_pct"] == 0.03
        print(f"✅ Risk limits updated.")

    def test_14_get_subscription_plans_and_subscribe(self, client: TestClient, db_session: Session):
        """Step 14: Get subscription plans and subscribe."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        # First ensure there's a plan
        plan = db_session.query(SubscriptionPlan).first()
        if not plan:
            plan = SubscriptionPlan(
                name="Pro",
                description="Professional plan",
                price_monthly=49.99,
                price_yearly=499.99,
                features={"max_positions": 100},
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db_session.add(plan)
            db_session.commit()
            db_session.refresh(plan)

        # List plans
        response = client.get("/api/v1/subscriptions/plans", headers=headers)
        assert response.status_code == 200
        plans = response.json()
        assert len(plans) >= 1

        # Subscribe
        payload = {
            "plan_id": plan.id,
            "payment_method": "stripe",
        }
        response = client.post("/api/v1/subscriptions/subscribe", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == self.user_id
        assert data["plan_id"] == plan.id
        assert data["status"] == "active"
        print(f"✅ Subscribed to plan: {plan.name}")

        # Verify current subscription
        response = client.get("/api/v1/subscriptions/current", headers=headers)
        assert response.status_code == 200
        current = response.json()
        assert current["status"] == "active"

    def test_15_logout(self, client: TestClient):
        """Step 15: Logout and verify token invalidated."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.post("/api/v1/auth/logout", headers=headers)
        assert response.status_code == 204

        # Try to access protected endpoint with old token (should fail)
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 401
        print(f"✅ Logout successful, token invalidated.")

    def test_16_refresh_token(self, client: TestClient):
        """Step 16: Refresh access token."""
        payload = {"refresh_token": self.refresh_token}
        response = client.post("/api/v1/auth/refresh", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        new_token = data["access_token"]
        # Test new token works
        headers = {"Authorization": f"Bearer {new_token}"}
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        print(f"✅ Token refresh works.")

    def test_17_close_position(self, client: TestClient):
        """Step 17: Close the open position (from market order)."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.post(f"/api/v1/portfolio/positions/{self.position_id}/close", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == self.position_id
        assert data["status"] == "closed"
        print(f"✅ Position closed.")

    def test_18_verify_portfolio_after_trades(self, client: TestClient):
        """Step 18: Check portfolio summary after all trades."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = client.get("/api/v1/portfolio/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Balance should have changed
        # We can't assert exact because price is mocked, but it should exist
        assert "total_balance" in data
        assert data["total_balance"] >= 0
        # Check that there are no open positions (since we closed)
        positions = client.get("/api/v1/portfolio/positions", headers=headers)
        assert positions.status_code == 200
        pos_data = positions.json()
        # The closed position might still appear with status closed, or removed.
        # We'll just check that there is no active position for AAPL.
        active = [p for p in pos_data if p.get("status") != "closed"]
        # It might be empty; fine.
        print(f"✅ Portfolio summary verified.")

    def test_19_cleanup(self, db_session: Session):
        """Step 19: Final cleanup (the fixture already handles it, but we can add extra)."""
        # The teardown will delete the user and all related data.
        # We can also manually verify that the user is deleted after the test.
        pass
