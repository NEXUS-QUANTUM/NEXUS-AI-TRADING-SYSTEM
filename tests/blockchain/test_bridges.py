# tests/blockchain/test_bridges.py
"""
Bridge Tests for the NEXUS AI Trading System.

This module contains comprehensive tests for cross-chain bridge functionality:
- BaseBridge abstract class and implementations
- BridgeManager for orchestration
- Bridge asset transfers (wrapping, unwrapping, cross-chain)
- Bridge fees and gas calculations
- Bridge event monitoring and status tracking
- Bridge validation and security
- Bridge analytics and reporting

All tests use mocked blockchain providers and contract interactions.
"""

import asyncio
from decimal import Decimal
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockchain.bridges.base_bridge import BaseBridge
from blockchain.bridges.bridge_manager import BridgeManager
from blockchain.bridges.ethereum_bridge import EthereumBridge
from blockchain.bridges.binance_bridge import BinanceBridge
from blockchain.bridges.polygon_bridge import PolygonBridge
from blockchain.bridges.arbitrum_bridge import ArbitrumBridge
from blockchain.bridges.optimism_bridge import OptimismBridge
from blockchain.bridges.avalanche_bridge import AvalancheBridge
from blockchain.bridges.solana_bridge import SolanaBridge
from blockchain.bridges.bridge_config import BridgeConfig
from blockchain.bridges.bridge_events import BridgeEventManager
from blockchain.bridges.bridge_fees import BridgeFeeCalculator
from blockchain.bridges.bridge_monitor import BridgeMonitor
from blockchain.bridges.bridge_security import BridgeSecurity
from blockchain.bridges.bridge_transaction import BridgeTransaction
from blockchain.bridges.bridge_validator import BridgeValidator
from blockchain.bridges.cross_chain_swap import CrossChainSwap

pytest_plugins = ["tests.blockchain.conftest"]


# ============================== BASE BRIDGE TESTS ==============================

class TestBaseBridge:
    """Test the BaseBridge abstract class and its methods."""

    def test_base_bridge_initialization(self):
        """Test that BaseBridge initializes with required params."""
        bridge = BaseBridge(name="TestBridge", chain_id_from=1, chain_id_to=56)
        assert bridge.name == "TestBridge"
        assert bridge.chain_id_from == 1
        assert bridge.chain_id_to == 56
        assert bridge.is_active is True

    async def test_bridge_asset_not_implemented(self):
        """Test that bridge_asset raises NotImplementedError."""
        bridge = BaseBridge(name="Test", chain_id_from=1, chain_id_to=56)
        with pytest.raises(NotImplementedError):
            await bridge.bridge_asset("ETH", 1.0, "0xfrom", "0xto")

    async def test_get_quote_not_implemented(self):
        """Test that get_quote raises NotImplementedError."""
        bridge = BaseBridge(name="Test", chain_id_from=1, chain_id_to=56)
        with pytest.raises(NotImplementedError):
            await bridge.get_quote("ETH", 1.0, "0xfrom", "0xto")

    def test_get_bridge_info(self):
        """Test retrieving bridge information."""
        bridge = BaseBridge(name="Test", chain_id_from=1, chain_id_to=56)
        info = bridge.get_bridge_info()
        assert info["name"] == "Test"
        assert info["chain_id_from"] == 1
        assert info["chain_id_to"] == 56
        assert "supported_assets" in info


# ============================== BRIDGE IMPLEMENTATION TESTS ==============================

class TestEthereumBridge:
    """Test the EthereumBridge implementation."""

    @pytest.fixture
    def eth_bridge(self, web3_client_service, mock_erc20_contract):
        """Return an EthereumBridge instance with mocked dependencies."""
        bridge = EthereumBridge(
            name="Ethereum-BSC",
            chain_id_from=1,
            chain_id_to=56,
            web3_client=web3_client_service,
            bridge_contract_address="0x" + "a" * 40,
        )
        # Mock the contract interaction
        bridge.bridge_contract = mock_erc20_contract
        return bridge

    async def test_bridge_asset_eth(self, eth_bridge):
        """Test bridging native ETH from Ethereum to BSC."""
        # Mock the deposit function
        with patch.object(eth_bridge.bridge_contract.functions, "deposit") as mock_deposit:
            mock_deposit.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(eth_bridge.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "b" * 64
                with patch.object(eth_bridge.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "b" * 64}
                    result = await eth_bridge.bridge_asset(
                        asset="ETH",
                        amount=1.0,
                        from_address="0xfrom",
                        to_address="0xto",
                        recipient="0xrecv",
                    )
                    assert result["tx_hash"] == "0x" + "b" * 64
                    assert result["status"] == "completed"
                    mock_deposit.assert_called_once()

    async def test_bridge_asset_erc20(self, eth_bridge, mock_erc20_contract):
        """Test bridging an ERC20 token from Ethereum to BSC."""
        # Mock the approve and deposit flow
        with patch.object(mock_erc20_contract.functions, "approve") as mock_approve:
            mock_approve.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(mock_erc20_contract.functions, "deposit") as mock_deposit:
                mock_deposit.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
                with patch.object(eth_bridge.web3_client.eth, "send_transaction") as mock_send:
                    mock_send.side_effect = ["0x" + "c" * 64, "0x" + "d" * 64]
                    with patch.object(eth_bridge.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                        mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "d" * 64}
                        result = await eth_bridge.bridge_asset(
                            asset="USDC",
                            amount=1000.0,
                            from_address="0xfrom",
                            to_address="0xto",
                            recipient="0xrecv",
                        )
                        assert result["tx_hash"] == "0x" + "d" * 64

    async def test_get_quote(self, eth_bridge):
        """Test getting a bridge quote."""
        # Mock the fee calculation
        with patch.object(eth_bridge, "_calculate_fee", return_value={"fee": 0.001, "gas_estimate": 0.0001}):
            quote = await eth_bridge.get_quote(
                asset="ETH",
                amount=1.0,
                from_address="0xfrom",
                to_address="0xto",
            )
            assert quote["fee"] == 0.001
            assert quote["gas_estimate"] == 0.0001
            assert quote["estimated_time"] > 0

    def test_validate_transaction(self, eth_bridge):
        """Test transaction validation."""
        # Valid transaction
        tx = {"amount": 1.0, "asset": "ETH", "from": "0xfrom", "to": "0xto"}
        is_valid = eth_bridge.validate_transaction(tx)
        assert is_valid is True

        # Invalid: missing amount
        tx_invalid = {"asset": "ETH", "from": "0xfrom", "to": "0xto"}
        is_valid = eth_bridge.validate_transaction(tx_invalid)
        assert is_valid is False

        # Invalid: unsupported asset
        tx_invalid2 = {"amount": 1.0, "asset": "XXX", "from": "0xfrom", "to": "0xto"}
        is_valid = eth_bridge.validate_transaction(tx_invalid2)
        assert is_valid is False


class TestBinanceBridge:
    """Test the BinanceBridge implementation."""

    @pytest.fixture
    def bnb_bridge(self, web3_client_service, mock_erc20_contract):
        """Return a BinanceBridge instance."""
        bridge = BinanceBridge(
            name="BSC-Ethereum",
            chain_id_from=56,
            chain_id_to=1,
            web3_client=web3_client_service,
            bridge_contract_address="0x" + "b" * 40,
        )
        bridge.bridge_contract = mock_erc20_contract
        return bridge

    async def test_bridge_asset_bnb(self, bnb_bridge):
        """Test bridging BNB from BSC to Ethereum."""
        with patch.object(bnb_bridge.bridge_contract.functions, "deposit") as mock_deposit:
            mock_deposit.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(bnb_bridge.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "e" * 64
                with patch.object(bnb_bridge.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "e" * 64}
                    result = await bnb_bridge.bridge_asset(
                        asset="BNB",
                        amount=10.0,
                        from_address="0xfrom",
                        to_address="0xto",
                    )
                    assert result["tx_hash"] == "0x" + "e" * 64


class TestPolygonBridge:
    """Test the PolygonBridge implementation."""

    @pytest.fixture
    def polygon_bridge(self, web3_client_service, mock_erc20_contract):
        """Return a PolygonBridge instance."""
        bridge = PolygonBridge(
            name="Polygon-Ethereum",
            chain_id_from=137,
            chain_id_to=1,
            web3_client=web3_client_service,
            bridge_contract_address="0x" + "c" * 40,
        )
        bridge.bridge_contract = mock_erc20_contract
        return bridge

    async def test_bridge_asset_matic(self, polygon_bridge):
        """Test bridging MATIC from Polygon to Ethereum."""
        with patch.object(polygon_bridge.bridge_contract.functions, "deposit") as mock_deposit:
            mock_deposit.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(polygon_bridge.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "f" * 64
                with patch.object(polygon_bridge.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "f" * 64}
                    result = await polygon_bridge.bridge_asset(
                        asset="MATIC",
                        amount=100.0,
                        from_address="0xfrom",
                        to_address="0xto",
                    )
                    assert result["tx_hash"] == "0x" + "f" * 64


# ============================== BRIDGE MANAGER TESTS ==============================

class TestBridgeManager:
    """Test the BridgeManager orchestrating multiple bridges."""

    @pytest.fixture
    def bridge_manager(self):
        """Return a BridgeManager instance with mock bridges."""
        manager = BridgeManager()
        # Add mock bridges
        mock_bridge1 = AsyncMock(spec=BaseBridge)
        mock_bridge1.name = "Eth-BSC"
        mock_bridge1.chain_id_from = 1
        mock_bridge1.chain_id_to = 56
        mock_bridge1.bridge_asset.return_value = {"tx_hash": "0x123", "status": "pending"}
        mock_bridge1.get_quote.return_value = {"fee": 0.001, "gas_estimate": 0.0001}

        mock_bridge2 = AsyncMock(spec=BaseBridge)
        mock_bridge2.name = "Eth-Polygon"
        mock_bridge2.chain_id_from = 1
        mock_bridge2.chain_id_to = 137
        mock_bridge2.bridge_asset.return_value = {"tx_hash": "0x456", "status": "pending"}

        manager.add_bridge(mock_bridge1)
        manager.add_bridge(mock_bridge2)
        return manager

    def test_add_bridge(self, bridge_manager):
        """Test adding a bridge to the manager."""
        new_bridge = AsyncMock()
        new_bridge.name = "Eth-Arbitrum"
        bridge_manager.add_bridge(new_bridge)
        assert "Eth-Arbitrum" in bridge_manager.bridges

    def test_get_bridge(self, bridge_manager):
        """Test retrieving a bridge by name."""
        bridge = bridge_manager.get_bridge("Eth-BSC")
        assert bridge.name == "Eth-BSC"

    def test_get_bridge_not_found(self, bridge_manager):
        """Test retrieving a non-existent bridge raises error."""
        with pytest.raises(KeyError):
            bridge_manager.get_bridge("Unknown")

    async def test_bridge_asset_with_manager(self, bridge_manager):
        """Test bridging asset using the manager."""
        result = await bridge_manager.bridge_asset(
            bridge_name="Eth-BSC",
            asset="ETH",
            amount=1.0,
            from_chain=1,
            to_chain=56,
            recipient="0xrecv",
        )
        assert result["tx_hash"] == "0x123"
        # Verify the bridge was called
        bridge = bridge_manager.get_bridge("Eth-BSC")
        bridge.bridge_asset.assert_called_once_with(
            asset="ETH",
            amount=1.0,
            from_address=None,  # may be None
            to_address=None,    # may be None
            recipient="0xrecv",
        )

    async def test_get_quote_with_manager(self, bridge_manager):
        """Test getting a quote using the manager."""
        quote = await bridge_manager.get_bridge_quote(
            bridge_name="Eth-BSC",
            asset="ETH",
            amount=1.0,
            from_chain=1,
            to_chain=56,
        )
        assert quote["fee"] == 0.001
        bridge = bridge_manager.get_bridge("Eth-BSC")
        bridge.get_quote.assert_called_once_with(
            asset="ETH",
            amount=1.0,
            from_address=None,
            to_address=None,
        )

    async def test_bridge_asset_with_auto_bridge_detection(self, bridge_manager):
        """Test that manager automatically selects the correct bridge based on chains."""
        # Find bridge by chain pair
        result = await bridge_manager.bridge_asset(
            asset="ETH",
            amount=1.0,
            from_chain=1,
            to_chain=137,
            recipient="0xrecv",
        )
        assert result["tx_hash"] == "0x456"  # Eth-Polygon was used
        # Verify it called the correct bridge
        bridge = bridge_manager.get_bridge("Eth-Polygon")
        bridge.bridge_asset.assert_called_once()


# ============================== BRIDGE FEE CALCULATOR TESTS ==============================

class TestBridgeFeeCalculator:
    """Test the BridgeFeeCalculator for fee calculations."""

    @pytest.fixture
    def fee_calculator(self):
        """Return a BridgeFeeCalculator instance."""
        return BridgeFeeCalculator()

    def test_calculate_fee_fixed(self, fee_calculator):
        """Test fixed fee calculation."""
        fee = fee_calculator.calculate_fee(
            asset="ETH",
            amount=1.0,
            fee_type="fixed",
            fee_rate=0.001,
            min_fee=0.0005,
            max_fee=0.01,
        )
        assert fee == 0.001  # 0.1% of 1 = 0.001

    def test_calculate_fee_percentage(self, fee_calculator):
        """Test percentage-based fee."""
        fee = fee_calculator.calculate_fee(
            asset="ETH",
            amount=10.0,
            fee_type="percentage",
            fee_rate=0.002,  # 0.2%
            min_fee=0.001,
            max_fee=0.05,
        )
        assert fee == 0.02  # 0.2% of 10 = 0.02

    def test_calculate_fee_with_min(self, fee_calculator):
        """Test fee calculation with minimum fee."""
        fee = fee_calculator.calculate_fee(
            asset="ETH",
            amount=0.1,
            fee_type="percentage",
            fee_rate=0.01,  # 1%
            min_fee=0.005,
            max_fee=0.1,
        )
        # 1% of 0.1 = 0.001, but min_fee=0.005, so fee = 0.005
        assert fee == 0.005

    def test_calculate_fee_with_max(self, fee_calculator):
        """Test fee calculation with maximum fee."""
        fee = fee_calculator.calculate_fee(
            asset="ETH",
            amount=100.0,
            fee_type="percentage",
            fee_rate=0.01,  # 1%
            min_fee=0.005,
            max_fee=0.5,
        )
        # 1% of 100 = 1.0, but max_fee=0.5, so fee = 0.5
        assert fee == 0.5

    def test_calculate_gas_estimate(self, fee_calculator):
        """Test gas estimation for a bridge transaction."""
        gas_estimate = fee_calculator.calculate_gas_estimate(
            bridge_name="Eth-BSC",
            asset="ETH",
            amount=1.0,
            gas_price=100e9,  # 100 Gwei
            gas_limit=21000,
        )
        # gas_price * gas_limit = 100e9 * 21000 = 2.1e15 wei = 0.0021 ETH
        assert gas_estimate == 0.0021


# ============================== BRIDGE MONITOR TESTS ==============================

class TestBridgeMonitor:
    """Test the BridgeMonitor for monitoring bridge transactions."""

    @pytest.fixture
    def bridge_monitor(self):
        """Return a BridgeMonitor instance with mocked dependencies."""
        monitor = BridgeMonitor()
        # Mock the event listener
        monitor.event_manager = AsyncMock()
        return monitor

    async def test_check_transaction_status(self, bridge_monitor):
        """Test checking status of a bridge transaction."""
        tx_hash = "0x" + "a" * 64
        with patch.object(bridge_monitor, "_get_transaction_receipt") as mock_receipt:
            mock_receipt.return_value = {"status": 1, "blockNumber": 12345}
            status = await bridge_monitor.check_transaction_status(tx_hash)
            assert status["status"] == "completed"
            assert status["block_number"] == 12345

    async def test_monitor_bridge_events(self, bridge_monitor):
        """Test monitoring bridge events."""
        # Simulate starting monitoring
        with patch.object(bridge_monitor.event_manager, "start_monitoring") as mock_start:
            await bridge_monitor.start_monitoring("Eth-BSC")
            mock_start.assert_called_once_with("Eth-BSC")

    async def test_alert_on_transaction_failure(self, bridge_monitor):
        """Test that alerts are triggered on transaction failure."""
        # Mock a failed transaction
        tx_hash = "0x" + "b" * 64
        with patch.object(bridge_monitor, "_get_transaction_receipt") as mock_receipt:
            mock_receipt.return_value = {"status": 0, "blockNumber": 12345}
            with patch.object(bridge_monitor, "_send_alert") as mock_alert:
                await bridge_monitor.check_transaction_status(tx_hash)
                mock_alert.assert_called_once_with(f"Bridge transaction {tx_hash} failed.")


# ============================== BRIDGE SECURITY TESTS ==============================

class TestBridgeSecurity:
    """Test the BridgeSecurity module for validation and protection."""

    @pytest.fixture
    def bridge_security(self):
        """Return a BridgeSecurity instance."""
        return BridgeSecurity()

    def test_validate_address(self, bridge_security):
        """Test address validation."""
        valid_address = "0x" + "a" * 40
        invalid_address = "0x" + "a" * 39
        assert bridge_security.validate_address(valid_address) is True
        assert bridge_security.validate_address(invalid_address) is False
        assert bridge_security.validate_address("") is False

    def test_validate_amount(self, bridge_security):
        """Test amount validation."""
        assert bridge_security.validate_amount("ETH", 1.0) is True
        assert bridge_security.validate_amount("ETH", -1.0) is False
        assert bridge_security.validate_amount("ETH", 0) is False
        assert bridge_security.validate_amount("ETH", 1e-9) is True  # very small

    def test_check_blacklist(self, bridge_security):
        """Test address blacklist check."""
        blacklisted = "0x" + "b" * 40
        bridge_security.add_to_blacklist(blacklisted)
        assert bridge_security.is_blacklisted(blacklisted) is True
        assert bridge_security.is_blacklisted("0x" + "c" * 40) is False

    def test_check_whitelist(self, bridge_security):
        """Test address whitelist check."""
        whitelisted = "0x" + "w" * 40
        bridge_security.add_to_whitelist(whitelisted)
        assert bridge_security.is_whitelisted(whitelisted) is True
        assert bridge_security.is_whitelisted("0x" + "x" * 40) is False


# ============================== BRIDGE VALIDATOR TESTS ==============================

class TestBridgeValidator:
    """Test the BridgeValidator for transaction validation."""

    @pytest.fixture
    def bridge_validator(self):
        """Return a BridgeValidator instance."""
        return BridgeValidator()

    def test_validate_transaction(self, bridge_validator):
        """Test validating a bridge transaction."""
        tx = {
            "asset": "ETH",
            "amount": 1.0,
            "from_address": "0x" + "a" * 40,
            "to_address": "0x" + "b" * 40,
            "chain_from": 1,
            "chain_to": 56,
        }
        result, errors = bridge_validator.validate_transaction(tx)
        assert result is True
        assert len(errors) == 0

    def test_validate_transaction_missing_fields(self, bridge_validator):
        """Test validation with missing fields."""
        tx = {"asset": "ETH", "amount": 1.0}  # missing addresses
        result, errors = bridge_validator.validate_transaction(tx)
        assert result is False
        assert "from_address" in str(errors)
        assert "to_address" in str(errors)

    def test_validate_transaction_invalid_amount(self, bridge_validator):
        """Test validation with invalid amount."""
        tx = {
            "asset": "ETH",
            "amount": -1.0,
            "from_address": "0x" + "a" * 40,
            "to_address": "0x" + "b" * 40,
            "chain_from": 1,
            "chain_to": 56,
        }
        result, errors = bridge_validator.validate_transaction(tx)
        assert result is False
        assert "amount" in str(errors)


# ============================== BRIDGE TRANSACTION TESTS ==============================

class TestBridgeTransaction:
    """Test the BridgeTransaction model and utilities."""

    def test_create_transaction(self):
        """Test creating a bridge transaction object."""
        tx = BridgeTransaction(
            bridge_name="Eth-BSC",
            asset="ETH",
            amount=1.0,
            from_address="0xfrom",
            to_address="0xto",
            tx_hash="0x123",
            status="pending",
            created_at=1234567890,
        )
        assert tx.bridge_name == "Eth-BSC"
        assert tx.amount == 1.0
        assert tx.status == "pending"

    def test_transaction_to_dict(self):
        """Test converting transaction to dict."""
        tx = BridgeTransaction(
            bridge_name="Eth-BSC",
            asset="ETH",
            amount=1.0,
            from_address="0xfrom",
            to_address="0xto",
        )
        tx_dict = tx.to_dict()
        assert tx_dict["bridge_name"] == "Eth-BSC"
        assert "tx_hash" in tx_dict

    def test_transaction_update_status(self):
        """Test updating transaction status."""
        tx = BridgeTransaction(bridge_name="Eth-BSC", asset="ETH", amount=1.0, from_address="0xfrom", to_address="0xto")
        tx.update_status("completed")
        assert tx.status == "completed"
        assert tx.completed_at is not None


# ============================== CROSS-CHAIN SWAP TESTS ==============================

class TestCrossChainSwap:
    """Test the CrossChainSwap functionality for swapping tokens across chains."""

    @pytest.fixture
    def cross_chain_swap(self, bridge_manager):
        """Return a CrossChainSwap instance with a bridge manager."""
        return CrossChainSwap(bridge_manager)

    async def test_swap_eth_to_bsc(self, cross_chain_swap):
        """Test swapping ETH on Ethereum to BNB on BSC."""
        # Mock the bridge manager's bridge_asset
        with patch.object(cross_chain_swap.bridge_manager, "bridge_asset") as mock_bridge:
            mock_bridge.return_value = {"tx_hash": "0x123", "status": "pending"}
            result = await cross_chain_swap.swap(
                from_chain=1,
                to_chain=56,
                from_asset="ETH",
                to_asset="BNB",
                amount=1.0,
                from_address="0xfrom",
                to_address="0xto",
                recipient="0xrecv",
            )
            assert result["tx_hash"] == "0x123"
            mock_bridge.assert_called_once_with(
                bridge_name="Eth-BSC",  # based on chain pair
                asset="ETH",
                amount=1.0,
                from_chain=1,
                to_chain=56,
                recipient="0xrecv",
            )

    async def test_swap_require_liquidity_check(self, cross_chain_swap):
        """Test that swap checks for sufficient liquidity."""
        # Mock the liquidity check to return insufficient
        with patch.object(cross_chain_swap, "_check_liquidity") as mock_liquidity:
            mock_liquidity.return_value = {"available": 0.5, "required": 1.0}
            with pytest.raises(ValueError) as exc:
                await cross_chain_swap.swap(
                    from_chain=1,
                    to_chain=56,
                    from_asset="ETH",
                    to_asset="BNB",
                    amount=1.0,
                    from_address="0xfrom",
                    to_address="0xto",
                )
            assert "insufficient liquidity" in str(exc.value).lower()


# ============================== BRIDGE EVENT MANAGER TESTS ==============================

class TestBridgeEventManager:
    """Test the BridgeEventManager for handling bridge events."""

    @pytest.fixture
    def event_manager(self):
        """Return a BridgeEventManager instance."""
        return BridgeEventManager()

    async def test_register_listener(self, event_manager):
        """Test registering an event listener."""
        listener = AsyncMock()
        event_manager.register_listener("BridgeDeposit", listener)
        assert "BridgeDeposit" in event_manager.listeners
        assert listener in event_manager.listeners["BridgeDeposit"]

    async def test_emit_event(self, event_manager):
        """Test emitting an event to listeners."""
        listener = AsyncMock()
        event_manager.register_listener("BridgeDeposit", listener)
        event_data = {"amount": 1.0, "recipient": "0x123"}
        await event_manager.emit("BridgeDeposit", event_data)
        listener.assert_called_once_with(event_data)

    async def test_remove_listener(self, event_manager):
        """Test removing a listener."""
        listener = AsyncMock()
        event_manager.register_listener("BridgeDeposit", listener)
        event_manager.remove_listener("BridgeDeposit", listener)
        assert listener not in event_manager.listeners.get("BridgeDeposit", [])

    async def test_event_handling_exception(self, event_manager):
        """Test that exceptions in listeners are caught."""
        listener = AsyncMock(side_effect=Exception("Test error"))
        event_manager.register_listener("BridgeDeposit", listener)
        # Should not raise
        await event_manager.emit("BridgeDeposit", {})


# ============================== INTEGRATION TESTS ==============================

class TestBridgeIntegration:
    """Integration tests for bridge components working together."""

    async def test_full_bridge_flow(self, bridge_manager, bridge_fee_calculator, bridge_validator, bridge_monitor):
        """Test a complete bridge flow: validation -> fee -> bridge -> monitor."""
        # Simulate a bridge transaction
        tx_data = {
            "bridge_name": "Eth-BSC",
            "asset": "ETH",
            "amount": 1.0,
            "from_address": "0xfrom",
            "to_address": "0xto",
            "recipient": "0xrecv",
        }

        # 1. Validate
        valid, errors = bridge_validator.validate_transaction(tx_data)
        assert valid is True

        # 2. Calculate fee
        fee = bridge_fee_calculator.calculate_fee(
            asset=tx_data["asset"],
            amount=tx_data["amount"],
            fee_type="percentage",
            fee_rate=0.001,
            min_fee=0.0005,
            max_fee=0.01,
        )
        assert fee > 0

        # 3. Execute bridge (mock)
        with patch.object(bridge_manager, "bridge_asset") as mock_bridge:
            mock_bridge.return_value = {"tx_hash": "0x123", "status": "pending", "fee": fee}
            result = await bridge_manager.bridge_asset(
                bridge_name=tx_data["bridge_name"],
                asset=tx_data["asset"],
                amount=tx_data["amount"],
                from_chain=1,
                to_chain=56,
                recipient=tx_data["recipient"],
            )
            assert result["tx_hash"] == "0x123"

        # 4. Monitor transaction
        with patch.object(bridge_monitor, "check_transaction_status") as mock_status:
            mock_status.return_value = {"status": "completed", "block_number": 12345}
            status = await bridge_monitor.check_transaction_status("0x123")
            assert status["status"] == "completed"

    async def test_bridge_with_gas_estimation(self, bridge_manager, bridge_fee_calculator):
        """Test bridge including gas estimation."""
        # Get quote which includes gas
        with patch.object(bridge_manager.get_bridge("Eth-BSC"), "get_quote") as mock_quote:
            mock_quote.return_value = {
                "fee": 0.001,
                "gas_estimate": 0.0021,
                "estimated_time": 120,
            }
            quote = await bridge_manager.get_bridge_quote(
                bridge_name="Eth-BSC",
                asset="ETH",
                amount=1.0,
                from_chain=1,
                to_chain=56,
            )
            assert quote["gas_estimate"] == 0.0021

        # Calculate total cost
        total_cost = quote["fee"] + quote["gas_estimate"]
        assert total_cost == 0.0031

    async def test_bridge_security_checks(self, bridge_manager, bridge_security):
        """Test that security checks are applied before bridging."""
        # Add a blacklisted address
        blacklisted = "0x" + "b" * 40
        bridge_security.add_to_blacklist(blacklisted)

        # Attempt to bridge from blacklisted address
        with patch.object(bridge_manager, "bridge_asset") as mock_bridge:
            # The bridge manager should check security before calling bridge.
            # We'll mock the security check to return False.
            with patch.object(bridge_security, "is_blacklisted") as mock_blacklist:
                mock_blacklist.return_value = True
                with pytest.raises(ValueError) as exc:
                    await bridge_manager.bridge_asset(
                        bridge_name="Eth-BSC",
                        asset="ETH",
                        amount=1.0,
                        from_chain=1,
                        to_chain=56,
                        from_address=blacklisted,
                    )
                assert "blacklisted" in str(exc.value).lower()
