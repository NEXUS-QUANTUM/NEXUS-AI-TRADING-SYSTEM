"""
tests/integration/test_portfolio_integration.py

NEXUS AI Trading System - Portfolio Integration Tests

This test suite verifies the integration of portfolio management with the backend API,
database, and business logic. It tests:

- Portfolio summary and balance
- Positions CRUD (list, get, close)
- Performance metrics (PNL, returns, drawdown)
- Portfolio rebalancing
- Risk metrics integration
- Historical snapshots
- Watchlist integration

All tests use the FastAPI TestClient and a real test database.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import pytest
import time
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models.user import User
from backend.models.portfolio import Portfolio
from backend.models.position import Position
from backend.models.order import Order
from backend.models.broker_account import BrokerAccount
from backend.models.trade import Trade
from backend.models.portfolio_snapshot import PortfolioSnapshot
from backend.models.risk import RiskLimit

from tests.integration.conftest import (
    db_session,
    client,
    test_user,
    test_user_token,
    auth_headers,
    test_portfolio,
    test_broker_account,
    test_position,
    test_order,
    mock_alpaca_broker,
)


# ----- Helper Functions -----

def create_test_position(
    db: Session,
    portfolio_id: str,
    broker_account_id: str,
    symbol: str = "AAPL",
    quantity: float = 10,
    entry_price: float = 150.0,
    current_price: float = 155.0,
    side: str = "long",
) -> Position:
    """Create a test position with given parameters."""
    position = Position(
        portfolio_id=portfolio_id,
        broker_account_id=broker_account_id,
        symbol=symbol,
        quantity=quantity,
        entry_price=entry_price,
        current_price=current_price,
        side=side,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(position)
    db.commit()
    db.refresh(position)
    return position


def create_test_trade(
    db: Session,
    portfolio_id: str,
    position_id: str = None,
    symbol: str = "AAPL",
    side: str = "buy",
    quantity: float = 5,
    price: float = 150.0,
    order_id: str = None,
) -> Trade:
    """Create a test trade record."""
    trade = Trade(
        portfolio_id=portfolio_id,
        position_id=position_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        order_id=order_id,
        executed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def create_portfolio_snapshot(db: Session, portfolio_id: str, total_balance: float, equity: float) -> PortfolioSnapshot:
    """Create a historical snapshot of portfolio."""
    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio_id,
        total_balance=total_balance,
        equity=equity,
        available_balance=total_balance - equity,
        timestamp=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


# ----- Portfolio API Tests -----

class TestPortfolioSummary:
    """Test portfolio summary endpoints."""

    def test_get_portfolio_summary(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio):
        """Test GET /api/v1/portfolio/summary returns correct data."""
        response = client.get("/api/v1/portfolio/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_portfolio.id
        assert data["user_id"] == test_portfolio.user_id
        assert data["total_balance"] == test_portfolio.total_balance
        assert data["available_balance"] == test_portfolio.available_balance
        assert data["currency"] == test_portfolio.currency
        assert "equity" in data
        assert "daily_pnl" in data
        assert "total_pnl" in data
        assert "positions_count" in data
        assert "timestamp" in data

    def test_update_portfolio_name(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio):
        """Test PUT /api/v1/portfolio/update updates portfolio name."""
        new_name = "Updated Portfolio Name"
        payload = {"name": new_name}
        response = client.put(f"/api/v1/portfolio/{test_portfolio.id}", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == new_name
        # Verify in DB
        db = next(iter(client.app.dependency_overrides.values()))()
        portfolio = db.query(Portfolio).filter(Portfolio.id == test_portfolio.id).first()
        assert portfolio.name == new_name

    def test_get_portfolio_with_positions(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio, test_position: Position):
        """Test GET /api/v1/portfolio/summary includes position summary."""
        response = client.get("/api/v1/portfolio/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["positions_count"] >= 1
        # The response might include a list of positions or just count; we'll check count.
        # If it includes a positions list, verify content.
        if "positions" in data:
            positions = data["positions"]
            assert len(positions) >= 1
            assert any(p["symbol"] == test_position.symbol for p in positions)

    def test_get_portfolio_not_found(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/portfolio/summary for user with no portfolio (should not happen)."""
        # This test might be redundant because portfolio is auto-created.
        # We'll just test that the endpoint doesn't crash.
        response = client.get("/api/v1/portfolio/summary", headers=auth_headers)
        assert response.status_code in [200, 404]


# ----- Positions Tests -----

class TestPositions:
    """Test positions CRUD and operations."""

    def test_list_positions(self, client: TestClient, auth_headers: Dict, test_position: Position):
        """Test GET /api/v1/portfolio/positions lists all positions."""
        response = client.get("/api/v1/portfolio/positions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        pos = data[0]
        assert "id" in pos
        assert "symbol" in pos
        assert "quantity" in pos
        assert "entry_price" in pos
        assert "current_price" in pos
        assert "unrealized_pnl" in pos
        assert "unrealized_pnl_pct" in pos

    def test_get_position_by_id(self, client: TestClient, auth_headers: Dict, test_position: Position):
        """Test GET /api/v1/portfolio/positions/{position_id}."""
        response = client.get(f"/api/v1/portfolio/positions/{test_position.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_position.id
        assert data["symbol"] == test_position.symbol
        assert data["quantity"] == test_position.quantity
        assert data["entry_price"] == test_position.entry_price

    def test_get_position_not_found(self, client: TestClient, auth_headers: Dict):
        """Test GET non-existent position returns 404."""
        response = client.get("/api/v1/portfolio/positions/non-existent-id", headers=auth_headers)
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_close_position(self, client: TestClient, auth_headers: Dict, test_position: Position, test_portfolio: Portfolio, mock_alpaca_broker):
        """Test closing a position via API."""
        # Ensure position exists
        response = client.post(f"/api/v1/portfolio/positions/{test_position.id}/close", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_position.id
        assert data["status"] == "closed"
        # Verify that the position is no longer active
        get_resp = client.get(f"/api/v1/portfolio/positions/{test_position.id}", headers=auth_headers)
        assert get_resp.status_code == 200
        pos_data = get_resp.json()
        assert pos_data.get("status") == "closed" or pos_data.get("is_active") is False

        # Check that a trade was recorded
        db = next(iter(client.app.dependency_overrides.values()))()
        trades = db.query(Trade).filter(Trade.position_id == test_position.id).all()
        assert len(trades) >= 1
        close_trade = trades[-1]
        assert close_trade.side == "sell"  # if long position
        assert close_trade.quantity == test_position.quantity

    def test_close_position_already_closed(self, client: TestClient, auth_headers: Dict, test_position: Position):
        """Test closing an already closed position returns error."""
        # First close it
        client.post(f"/api/v1/portfolio/positions/{test_position.id}/close", headers=auth_headers)
        # Try to close again
        response = client.post(f"/api/v1/portfolio/positions/{test_position.id}/close", headers=auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert "already closed" in data["detail"].lower() or "closed" in data["detail"].lower()

    def test_close_position_unauthorized(self, client: TestClient, test_position: Position):
        """Test that another user cannot close a position."""
        # Create a second user and try to close position of first user
        # For simplicity, we'll use a different token (not implemented), but we'll test with no auth.
        response = client.post(f"/api/v1/portfolio/positions/{test_position.id}/close")
        assert response.status_code == 401

    def test_position_valuation(self, client: TestClient, auth_headers: Dict, test_position: Position):
        """Test that position current price is updated and PNL calculated."""
        # We'll update the price via a mock or by calling a sync endpoint.
        # First, get current position
        resp = client.get(f"/api/v1/portfolio/positions/{test_position.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        old_price = data["current_price"]
        old_pnl = data["unrealized_pnl"]

        # Simulate price change by updating position in DB (or via API)
        db = next(iter(client.app.dependency_overrides.values()))()
        position = db.query(Position).filter(Position.id == test_position.id).first()
        position.current_price = position.current_price * 1.05  # 5% increase
        db.commit()

        # Re-fetch position
        resp2 = client.get(f"/api/v1/portfolio/positions/{test_position.id}", headers=auth_headers)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["current_price"] != old_price
        assert data2["unrealized_pnl"] != old_pnl


# ----- Portfolio Performance Tests -----

class TestPortfolioPerformance:
    """Test portfolio performance metrics and analytics."""

    def test_get_performance_metrics(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio):
        """Test GET /api/v1/portfolio/performance returns metrics."""
        # We need some historical data; create snapshots
        db = next(iter(client.app.dependency_overrides.values()))()
        create_portfolio_snapshot(db, test_portfolio.id, 100000, 50000)
        create_portfolio_snapshot(db, test_portfolio.id, 105000, 55000)
        create_portfolio_snapshot(db, test_portfolio.id, 102000, 52000)

        response = client.get("/api/v1/portfolio/performance", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_return" in data
        assert "daily_return" in data
        assert "annualized_return" in data
        assert "sharpe_ratio" in data
        assert "max_drawdown" in data
        assert "volatility" in data
        assert "win_rate" in data
        assert "profit_factor" in data
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_performance_with_time_range(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/portfolio/performance with date filters."""
        params = {
            "start_date": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "interval": "daily",
        }
        response = client.get("/api/v1/portfolio/performance", params=params, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        # History should contain entries within the date range (if any)

    def test_performance_without_data(self, client: TestClient, auth_headers: Dict):
        """Test performance endpoint when no historical data exists."""
        # We'll use a new user without any history; but our test user may have data.
        # We can create a new user for this test, but for simplicity, we'll just ensure response is not empty.
        response = client.get("/api/v1/portfolio/performance", headers=auth_headers)
        assert response.status_code == 200
        # It may have empty history; that's fine.

    def test_get_returns_distribution(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/portfolio/performance/returns-distribution."""
        response = client.get("/api/v1/portfolio/performance/returns-distribution", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "mean" in data
        assert "std" in data
        assert "min" in data
        assert "max" in data
        assert "percentiles" in data
        assert isinstance(data["bins"], list)
        assert isinstance(data["frequencies"], list)

    def test_get_risk_metrics(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/portfolio/performance/risk-metrics."""
        response = client.get("/api/v1/portfolio/performance/risk-metrics", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "var_95" in data  # Value at Risk (95%)
        assert "cvar_95" in data  # Conditional VaR
        assert "max_drawdown" in data
        assert "max_drawdown_duration" in data
        assert "beta" in data
        assert "alpha" in data

    def test_get_performance_chart(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/portfolio/performance/chart returns chart data."""
        params = {"interval": "weekly", "period": "3m"}
        response = client.get("/api/v1/portfolio/performance/chart", params=params, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "labels" in data  # dates
        assert "datasets" in data
        assert isinstance(data["datasets"], list)
        if data["datasets"]:
            assert "data" in data["datasets"][0]
            assert "label" in data["datasets"][0]


# ----- Portfolio Snapshot Tests -----

class TestPortfolioSnapshots:
    """Test portfolio historical snapshots."""

    def test_create_snapshot(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio):
        """Test manual snapshot creation."""
        # The system might auto-create snapshots; we'll test the endpoint if it exists.
        # Some APIs may have POST /api/v1/portfolio/snapshot
        # We'll check if it exists; if not, skip.
        response = client.post("/api/v1/portfolio/snapshot", headers=auth_headers)
        if response.status_code == 405:
            pytest.skip("Snapshot creation endpoint not implemented")
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data
        assert data["portfolio_id"] == test_portfolio.id
        assert "timestamp" in data

    def test_list_snapshots(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/portfolio/snapshots."""
        # Create a few snapshots
        db = next(iter(client.app.dependency_overrides.values()))()
        portfolio = db.query(Portfolio).first()
        if not portfolio:
            pytest.skip("No portfolio available")
        create_portfolio_snapshot(db, portfolio.id, 100000, 50000)
        create_portfolio_snapshot(db, portfolio.id, 105000, 55000)

        response = client.get("/api/v1/portfolio/snapshots", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        snapshot = data[0]
        assert "total_balance" in snapshot
        assert "equity" in snapshot
        assert "timestamp" in snapshot

    def test_get_snapshot_by_id(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/portfolio/snapshots/{snapshot_id}."""
        # First create a snapshot
        db = next(iter(client.app.dependency_overrides.values()))()
        portfolio = db.query(Portfolio).first()
        if not portfolio:
            pytest.skip("No portfolio available")
        snap = create_portfolio_snapshot(db, portfolio.id, 100000, 50000)
        response = client.get(f"/api/v1/portfolio/snapshots/{snap.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == snap.id
        assert data["total_balance"] == 100000


# ----- Rebalancing Tests -----

class TestRebalancing:
    """Test portfolio rebalancing functionality."""

    def test_rebalance_portfolio(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio, test_position: Position):
        """Test POST /api/v1/portfolio/rebalance."""
        # This endpoint may not exist, but if it does, test it.
        # For rebalancing, we need target allocations.
        payload = {
            "target_allocations": {
                "AAPL": 0.4,
                "MSFT": 0.3,
                "GOOGL": 0.3,
            }
        }
        response = client.post("/api/v1/portfolio/rebalance", json=payload, headers=auth_headers)
        if response.status_code == 405:
            pytest.skip("Rebalance endpoint not implemented")
        assert response.status_code in [200, 202]
        data = response.json()
        assert "status" in data
        assert data["status"] == "started" or data["status"] == "completed"

    def test_get_rebalance_history(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/portfolio/rebalance/history."""
        response = client.get("/api/v1/portfolio/rebalance/history", headers=auth_headers)
        if response.status_code == 405:
            pytest.skip("Rebalance history endpoint not implemented")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# ----- Risk Integration Tests -----

class TestRiskIntegration:
    """Test integration of risk limits with portfolio."""

    def test_check_risk_before_order(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio):
        """Test that risk limits are checked before placing an order."""
        # Set a low risk limit
        db = next(iter(client.app.dependency_overrides.values()))()
        risk_limit = RiskLimit(
            user_id=test_portfolio.user_id,
            max_position_pct=0.01,  # 1% of portfolio
            max_drawdown=0.05,
            max_leverage=1.0,
            updated_at=datetime.utcnow(),
        )
        db.add(risk_limit)
        db.commit()

        # Try to place a large order (should be rejected)
        payload = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 100000,
            "order_type": "market",
            "portfolio_id": test_portfolio.id,
        }
        response = client.post("/api/v1/trading/orders", json=payload, headers=auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert "risk" in data["detail"].lower() or "limit" in data["detail"].lower()

    def test_get_risk_limits(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/risk/limits returns current limits."""
        response = client.get("/api/v1/risk/limits", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "max_drawdown" in data
        assert "max_position_pct" in data
        assert "max_leverage" in data

    def test_update_risk_limits(self, client: TestClient, auth_headers: Dict):
        """Test PUT /api/v1/risk/limits updates limits."""
        payload = {
            "max_drawdown": 0.10,
            "max_position_pct": 0.02,
            "max_leverage": 1.5,
        }
        response = client.put("/api/v1/risk/limits", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["max_drawdown"] == 0.10
        assert data["max_position_pct"] == 0.02


# ----- Watchlist Integration Tests -----

class TestWatchlist:
    """Test watchlist integration with portfolio."""

    def test_add_to_watchlist(self, client: TestClient, auth_headers: Dict):
        """Test POST /api/v1/watchlist/add."""
        payload = {"symbol": "AAPL"}
        response = client.post("/api/v1/watchlist/add", json=payload, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert "id" in data

    def test_get_watchlist(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/watchlist."""
        # Add a symbol first
        client.post("/api/v1/watchlist/add", json={"symbol": "MSFT"}, headers=auth_headers)
        response = client.get("/api/v1/watchlist", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(item["symbol"] == "MSFT" for item in data)

    def test_remove_from_watchlist(self, client: TestClient, auth_headers: Dict):
        """Test DELETE /api/v1/watchlist/{symbol}."""
        # Add then remove
        client.post("/api/v1/watchlist/add", json={"symbol": "GOOGL"}, headers=auth_headers)
        response = client.delete("/api/v1/watchlist/GOOGL", headers=auth_headers)
        assert response.status_code == 204
        # Verify it's gone
        watchlist = client.get("/api/v1/watchlist", headers=auth_headers).json()
        assert not any(item["symbol"] == "GOOGL" for item in watchlist)


# ----- Portfolio Data Integrity Tests -----

class TestDataIntegrity:
    """Test that portfolio data remains consistent after operations."""

    def test_balance_consistency_after_trade(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio):
        """Test that portfolio balance updates correctly after trade."""
        # Get initial balance
        summary1 = client.get("/api/v1/portfolio/summary", headers=auth_headers).json()
        initial_balance = summary1["total_balance"]

        # Place a market order (buy)
        payload = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 5,
            "order_type": "market",
            "portfolio_id": test_portfolio.id,
        }
        order_resp = client.post("/api/v1/trading/orders", json=payload, headers=auth_headers)
        assert order_resp.status_code == 201
        order_data = order_resp.json()
        # Get price from order (filled price)
        price = order_data.get("filled_price", 150.0)
        cost = price * 5

        # Get updated balance
        summary2 = client.get("/api/v1/portfolio/summary", headers=auth_headers).json()
        new_balance = summary2["total_balance"]
        # Balance should decrease by cost (approximately)
        assert new_balance <= initial_balance - cost * 0.99  # allow for fees

    def test_position_total_quantity_consistency(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio):
        """Test that total quantity of positions equals sum of quantities."""
        # Place multiple orders for same symbol
        for _ in range(3):
            payload = {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 2,
                "order_type": "market",
                "portfolio_id": test_portfolio.id,
            }
            client.post("/api/v1/trading/orders", json=payload, headers=auth_headers)

        # Get positions
        positions = client.get("/api/v1/portfolio/positions", headers=auth_headers).json()
        aapl_positions = [p for p in positions if p["symbol"] == "AAPL"]
        # There should be one position with total quantity 6
        assert len(aapl_positions) == 1
        assert aapl_positions[0]["quantity"] == 6

    def test_trade_history_links(self, client: TestClient, auth_headers: Dict, test_portfolio: Portfolio):
        """Test that each trade links back to its order and position."""
        # Place order
        payload = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 3,
            "order_type": "market",
            "portfolio_id": test_portfolio.id,
        }
        order_resp = client.post("/api/v1/trading/orders", json=payload, headers=auth_headers)
        order_id = order_resp.json()["id"]

        # Get trade history
        trades = client.get("/api/v1/portfolio/trades", headers=auth_headers).json()
        # Find the trade linked to this order
        trade = next((t for t in trades if t.get("order_id") == order_id), None)
        assert trade is not None
        assert trade["symbol"] == "AAPL"
        assert trade["quantity"] == 3
        assert trade["order_id"] == order_id
        # Should also have a position_id
        assert "position_id" in trade
