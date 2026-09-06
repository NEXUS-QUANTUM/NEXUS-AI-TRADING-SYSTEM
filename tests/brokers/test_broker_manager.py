# tests/brokers/test_broker_manager.py
"""
Broker Manager Tests.

This module tests the BrokerManager class, which is responsible for:
- Managing multiple broker accounts (add, remove, update)
- Connecting to brokers and maintaining sessions
- Health checks and failover
- Routing orders to appropriate brokers
- Managing broker credentials and encryption

All tests use mocked database sessions and broker instances.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brokers.broker_manager import BrokerManager
from backend.brokers.broker_factory import BrokerFactory
from backend.brokers.base_broker import BaseBroker
from backend.models.broker_account import BrokerAccount
from backend.models.user import User
from backend.services.broker_service import BrokerService


class TestBrokerManagerInitialization:
    """Test initialization and configuration of BrokerManager."""

    def test_broker_manager_initialization(self, async_db_session: AsyncSession):
        """Test that BrokerManager initializes with required dependencies."""
        manager = BrokerManager(db=async_db_session)
        assert manager.db is async_db_session
        assert manager.broker_factory is not None
        assert manager._broker_instances == {}

    def test_broker_manager_with_factory(self, async_db_session: AsyncSession, broker_factory: BrokerFactory):
        """Test that BrokerManager accepts a custom factory."""
        manager = BrokerManager(db=async_db_session, broker_factory=broker_factory)
        assert manager.broker_factory == broker_factory


class TestBrokerManagerAccountManagement:
    """Test account management operations (add, remove, update)."""

    async def test_add_broker_account(
        self,
        broker_manager: BrokerManager,
        test_user: User,
        async_db_session: AsyncSession,
    ):
        """Test adding a new broker account."""
        account_data = {
            "user_id": test_user.id,
            "broker_name": "binance",
            "api_key": "test_key",
            "api_secret": "test_secret",
            "label": "My Binance",
            "is_active": True,
        }
        account = await broker_manager.add_broker_account(**account_data)
        assert account.id is not None
        assert account.broker_name == "binance"
        assert account.user_id == test_user.id
        assert account.is_active is True
        # Verify it's in the DB
        db_account = await async_db_session.get(BrokerAccount, account.id)
        assert db_account is not None
        assert db_account.label == "My Binance"

    async def test_remove_broker_account(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
        async_db_session: AsyncSession,
    ):
        """Test removing a broker account."""
        account_id = test_broker_account.id
        await broker_manager.remove_broker_account(account_id)
        # Verify it's gone or marked inactive
        account = await async_db_session.get(BrokerAccount, account_id)
        # Depending on implementation, it may be soft-deleted; we'll assume soft delete with is_active=False
        if account:
            assert account.is_active is False
        else:
            # Hard delete
            assert account is None

    async def test_update_broker_account(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
        async_db_session: AsyncSession,
    ):
        """Test updating a broker account."""
        updates = {
            "label": "Updated Label",
            "api_key": "new_key",
            "is_active": False,
        }
        updated = await broker_manager.update_broker_account(test_broker_account.id, **updates)
        assert updated.label == "Updated Label"
        assert updated.api_key == "new_key"
        assert updated.is_active is False
        # Verify in DB
        db_account = await async_db_session.get(BrokerAccount, test_broker_account.id)
        assert db_account.label == "Updated Label"

    async def test_get_broker_account(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test retrieving a broker account by ID."""
        account = await broker_manager.get_broker_account(test_broker_account.id)
        assert account.id == test_broker_account.id
        assert account.broker_name == test_broker_account.broker_name

    async def test_list_broker_accounts(
        self,
        broker_manager: BrokerManager,
        test_user: User,
        async_db_session: AsyncSession,
    ):
        """Test listing broker accounts for a user."""
        # Create multiple accounts
        for i in range(3):
            await broker_manager.add_broker_account(
                user_id=test_user.id,
                broker_name="binance",
                api_key=f"key_{i}",
                api_secret=f"secret_{i}",
                label=f"Account {i}",
            )
        accounts = await broker_manager.list_broker_accounts(test_user.id)
        assert len(accounts) >= 3
        # All should belong to the user
        for acc in accounts:
            assert acc.user_id == test_user.id


class TestBrokerManagerConnection:
    """Test connecting to brokers and managing active sessions."""

    async def test_connect_broker(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test connecting to a broker account (instantiate broker client)."""
        # Mock the broker factory to return a mock broker
        mock_broker = AsyncMock(spec=BaseBroker)
        mock_broker.get_account = AsyncMock(return_value={"id": "test_acc", "balance": 1000})
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            broker = await broker_manager.connect_broker(test_broker_account.id)
            assert broker is mock_broker
            # Verify it's cached
            assert test_broker_account.id in broker_manager._broker_instances
            assert broker_manager._broker_instances[test_broker_account.id] == broker
            # Verify connection was tested
            mock_broker.get_account.assert_called_once()

    async def test_connect_broker_inactive_account(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
        async_db_session: AsyncSession,
    ):
        """Test connecting to an inactive account raises error."""
        test_broker_account.is_active = False
        await async_db_session.commit()
        with pytest.raises(ValueError) as exc:
            await broker_manager.connect_broker(test_broker_account.id)
        assert "inactive" in str(exc.value).lower()

    async def test_connect_broker_already_connected(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test that connecting to an already connected broker returns cached instance."""
        mock_broker = AsyncMock(spec=BaseBroker)
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            # First connect
            broker1 = await broker_manager.connect_broker(test_broker_account.id)
            # Second connect should return cached
            broker2 = await broker_manager.connect_broker(test_broker_account.id)
            assert broker1 is broker2
            # Factory should be called only once
            assert broker_manager.broker_factory.create_broker.call_count == 1

    async def test_disconnect_broker(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test disconnecting (removing) a broker instance from cache."""
        # First connect
        mock_broker = AsyncMock(spec=BaseBroker)
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            await broker_manager.connect_broker(test_broker_account.id)
            assert test_broker_account.id in broker_manager._broker_instances
            # Disconnect
            await broker_manager.disconnect_broker(test_broker_account.id)
            assert test_broker_account.id not in broker_manager._broker_instances

    async def test_get_broker_instance(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test getting a broker instance (auto-connect if not connected)."""
        mock_broker = AsyncMock(spec=BaseBroker)
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            # Should auto-connect
            broker = await broker_manager.get_broker_instance(test_broker_account.id)
            assert broker is mock_broker
            # Should be cached
            assert test_broker_account.id in broker_manager._broker_instances


class TestBrokerManagerHealth:
    """Test health checking and failover logic."""

    async def test_check_broker_health(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test checking the health of a broker."""
        mock_broker = AsyncMock(spec=BaseBroker)
        mock_broker.get_account = AsyncMock(return_value={"id": "test", "status": "ok"})
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            # Connect first
            await broker_manager.connect_broker(test_broker_account.id)
            # Check health
            healthy = await broker_manager.check_broker_health(test_broker_account.id)
            assert healthy is True
            mock_broker.get_account.assert_called()

    async def test_check_broker_health_unhealthy(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test health check returns False when broker is down."""
        mock_broker = AsyncMock(spec=BaseBroker)
        mock_broker.get_account = AsyncMock(side_effect=Exception("Connection refused"))
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            await broker_manager.connect_broker(test_broker_account.id)
            healthy = await broker_manager.check_broker_health(test_broker_account.id)
            assert healthy is False

    async def test_get_healthy_broker_for_user(
        self,
        broker_manager: BrokerManager,
        test_user: User,
        async_db_session: AsyncSession,
    ):
        """Test selecting a healthy broker for a user."""
        # Create multiple accounts, some healthy, some not.
        account1 = await broker_manager.add_broker_account(
            user_id=test_user.id,
            broker_name="binance",
            api_key="key1",
            api_secret="secret1",
            label="Broker 1",
        )
        account2 = await broker_manager.add_broker_account(
            user_id=test_user.id,
            broker_name="bybit",
            api_key="key2",
            api_secret="secret2",
            label="Broker 2",
        )
        # Mock health checks: account1 healthy, account2 unhealthy
        mock_broker1 = AsyncMock(spec=BaseBroker)
        mock_broker1.get_account = AsyncMock(return_value={"id": "ok"})
        mock_broker2 = AsyncMock(spec=BaseBroker)
        mock_broker2.get_account = AsyncMock(side_effect=Exception("Down"))

        with patch.object(broker_manager.broker_factory, "create_broker") as mock_factory:
            mock_factory.side_effect = [mock_broker1, mock_broker2]
            # Use get_healthy_broker
            healthy = await broker_manager.get_healthy_broker(test_user.id)
            # Should return account1
            assert healthy.id == account1.id
            # It should also be cached
            assert healthy.id in broker_manager._broker_instances


class TestBrokerManagerRouting:
    """Test routing orders/operations to the appropriate broker."""

    async def test_route_order_to_broker(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test that order placement is routed to the correct broker instance."""
        mock_broker = AsyncMock(spec=BaseBroker)
        mock_broker.place_order = AsyncMock(return_value={"id": "ord_123", "status": "filled"})
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            # Connect broker
            await broker_manager.connect_broker(test_broker_account.id)
            # Place order via manager
            result = await broker_manager.place_order(
                account_id=test_broker_account.id,
                symbol="BTC-USD",
                side="buy",
                order_type="market",
                quantity=1.0,
            )
            assert result["id"] == "ord_123"
            mock_broker.place_order.assert_called_once_with(
                symbol="BTC-USD",
                side="buy",
                order_type="market",
                quantity=1.0,
                price=None,
            )

    async def test_route_to_unhealthy_broker_raises(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test that using an unhealthy broker raises an error."""
        # Mock broker that fails on connection
        mock_broker = AsyncMock(spec=BaseBroker)
        mock_broker.get_account = AsyncMock(side_effect=Exception("Broker unavailable"))
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            with pytest.raises(Exception) as exc:
                await broker_manager.get_broker_instance(test_broker_account.id)
            assert "unavailable" in str(exc.value).lower() or "connection" in str(exc.value).lower()


class TestBrokerManagerErrorHandling:
    """Test error handling in broker manager operations."""

    async def test_add_account_with_invalid_broker_name(
        self,
        broker_manager: BrokerManager,
        test_user: User,
    ):
        """Test adding an account with an unsupported broker name."""
        with pytest.raises(ValueError) as exc:
            await broker_manager.add_broker_account(
                user_id=test_user.id,
                broker_name="unsupported",
                api_key="key",
                api_secret="secret",
            )
        assert "unsupported" in str(exc.value).lower()

    async def test_remove_nonexistent_account(
        self,
        broker_manager: BrokerManager,
    ):
        """Test removing a non-existent account."""
        with pytest.raises(ValueError) as exc:
            await broker_manager.remove_broker_account(99999)
        assert "not found" in str(exc.value).lower()

    async def test_update_nonexistent_account(
        self,
        broker_manager: BrokerManager,
    ):
        """Test updating a non-existent account."""
        with pytest.raises(ValueError) as exc:
            await broker_manager.update_broker_account(99999, label="New")
        assert "not found" in str(exc.value).lower()


class TestBrokerManagerCache:
    """Test the caching behavior of broker instances."""

    async def test_cache_cleared_on_account_update(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test that updating account details clears the cached broker instance."""
        # Connect
        mock_broker = AsyncMock(spec=BaseBroker)
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            await broker_manager.connect_broker(test_broker_account.id)
            assert test_broker_account.id in broker_manager._broker_instances
            # Update account (should invalidate cache)
            await broker_manager.update_broker_account(test_broker_account.id, label="New Label")
            # Cache should be cleared
            assert test_broker_account.id not in broker_manager._broker_instances

    async def test_cache_cleared_on_account_removal(
        self,
        broker_manager: BrokerManager,
        test_broker_account: BrokerAccount,
    ):
        """Test that removing an account clears the cached broker instance."""
        mock_broker = AsyncMock(spec=BaseBroker)
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            await broker_manager.connect_broker(test_broker_account.id)
            assert test_broker_account.id in broker_manager._broker_instances
            # Remove account
            await broker_manager.remove_broker_account(test_broker_account.id)
            assert test_broker_account.id not in broker_manager._broker_instances


class TestBrokerManagerIntegration:
    """Integration tests combining multiple operations."""

    async def test_full_broker_lifecycle(
        self,
        broker_manager: BrokerManager,
        test_user: User,
        async_db_session: AsyncSession,
    ):
        """Test adding, connecting, using, updating, and removing a broker."""
        # 1. Add account
        account = await broker_manager.add_broker_account(
            user_id=test_user.id,
            broker_name="binance",
            api_key="key",
            api_secret="secret",
            label="Test",
        )
        assert account.id is not None

        # 2. Connect
        mock_broker = AsyncMock(spec=BaseBroker)
        mock_broker.get_account = AsyncMock(return_value={"id": "acc"})
        mock_broker.place_order = AsyncMock(return_value={"id": "ord"})
        with patch.object(broker_manager.broker_factory, "create_broker", return_value=mock_broker):
            await broker_manager.connect_broker(account.id)
            # 3. Use it
            await broker_manager.place_order(account.id, "BTC-USD", "buy", "market", 1.0)
            # 4. Update
            await broker_manager.update_broker_account(account.id, label="Updated")
            # 5. Remove
            await broker_manager.remove_broker_account(account.id)
            # Verify cache cleared
            assert account.id not in broker_manager._broker_instances
