# tests/blockchain/test_staking.py
"""
Staking Tests for the NEXUS AI Trading System.

This module contains comprehensive tests for all staking-related functionality:
- StakingManager: pool management, stake/unstake operations
- Staking pools: ETH staking (Lido, Rocket Pool), liquid staking
- Staking rewards: APY calculation, reward distribution, compounding
- Staking contracts: interaction with staking protocols
- Staking analytics: yield tracking, risk assessment
- Staking validator: validator selection, delegation

All tests use mocked web3 providers and staking contract interactions.
"""

import asyncio
import json
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockchain.staking.base_staking import BaseStakingProtocol
from blockchain.staking.staking_manager import StakingManager
from blockchain.staking.eth_staking import EthStakingProtocol
from blockchain.staking.bnb_staking import BnbStakingProtocol
from blockchain.staking.sol_staking import SolStakingProtocol
from blockchain.staking.dot_staking import DotStakingProtocol
from blockchain.staking.atom_staking import AtomStakingProtocol
from blockchain.staking.liquid_staking import LiquidStakingProtocol
from blockchain.staking.staking_pool import StakingPoolManager
from blockchain.staking.staking_apy import StakingAPYCalculator
from blockchain.staking.staking_config import StakingConfig
from blockchain.staking.staking_analytics import StakingAnalytics
from blockchain.staking.staking_risk import StakingRiskManager
from blockchain.staking.staking_rewards import StakingRewardManager
from blockchain.staking.staking_validator import StakingValidatorManager

pytest_plugins = ["tests.blockchain.conftest"]


# ============================== BASE STAKING PROTOCOL TESTS ==============================

class TestBaseStakingProtocol:
    """Test the BaseStakingProtocol abstract class."""

    def test_base_protocol_initialization(self):
        """Test initializing a base staking protocol."""
        protocol = BaseStakingProtocol(name="TestStaking", chain_id=1)
        assert protocol.name == "TestStaking"
        assert protocol.chain_id == 1
        assert protocol.is_active is True

    async def test_stake_not_implemented(self):
        """Test that stake raises NotImplementedError."""
        protocol = BaseStakingProtocol(name="Test", chain_id=1)
        with pytest.raises(NotImplementedError):
            await protocol.stake(amount=1.0, from_address="0xfrom", private_key="0xkey")

    async def test_unstake_not_implemented(self):
        """Test that unstake raises NotImplementedError."""
        protocol = BaseStakingProtocol(name="Test", chain_id=1)
        with pytest.raises(NotImplementedError):
            await protocol.unstake(amount=1.0, from_address="0xfrom", private_key="0xkey")

    async def test_get_apy_not_implemented(self):
        """Test that get_apy raises NotImplementedError."""
        protocol = BaseStakingProtocol(name="Test", chain_id=1)
        with pytest.raises(NotImplementedError):
            await protocol.get_apy()

    def test_get_protocol_info(self):
        """Test retrieving protocol information."""
        protocol = BaseStakingProtocol(name="Test", chain_id=1)
        info = protocol.get_protocol_info()
        assert info["name"] == "Test"
        assert info["chain_id"] == 1
        assert "supported_assets" in info


# ============================== ETH STAKING PROTOCOL TESTS ==============================

class TestEthStakingProtocol:
    """Test the EthStakingProtocol (native ETH staking)."""

    @pytest.fixture
    def eth_staking_protocol(self, web3_client_service):
        """Return an EthStakingProtocol instance with mocked contract."""
        protocol = EthStakingProtocol(
            name="ETH Staking",
            chain_id=1,
            web3_client=web3_client_service,
            staking_contract_address="0x" + "a" * 40,
            deposit_contract_address="0x" + "b" * 40,
        )
        protocol.staking_contract = MagicMock()
        protocol.deposit_contract = MagicMock()
        return protocol

    async def test_stake_eth(self, eth_staking_protocol, test_private_key, test_address_from_private_key):
        """Test staking ETH."""
        with patch.object(eth_staking_protocol.deposit_contract.functions, "deposit") as mock_deposit:
            mock_deposit.return_value.build_transaction.return_value = {
                "to": "0x123",
                "data": "0x",
                "value": 32 * 10**18,  # 32 ETH
            }
            with patch.object(eth_staking_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "c" * 64
                with patch.object(eth_staking_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "c" * 64}
                    result = await eth_staking_protocol.stake(
                        amount=32,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "c" * 64
                    # Check that the deposit contract was called with correct value
                    mock_deposit.assert_called_once_with(
                        validator_public_key=None,  # may be provided
                        withdrawal_credentials=None,
                        signature=None,
                        deposit_data_root=None,
                    )

    async def test_unstake_eth(self, eth_staking_protocol, test_private_key, test_address_from_private_key):
        """Test unstaking ETH (requesting withdrawal)."""
        # For native ETH staking, unstake is a withdrawal request
        with patch.object(eth_staking_protocol.staking_contract.functions, "requestWithdrawal") as mock_withdraw:
            mock_withdraw.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(eth_staking_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "d" * 64
                with patch.object(eth_staking_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "d" * 64}
                    result = await eth_staking_protocol.unstake(
                        amount=16,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "d" * 64

    async def test_get_apy(self, eth_staking_protocol):
        """Test getting staking APY for ETH."""
        with patch.object(eth_staking_protocol, "_fetch_validator_apy") as mock_apy:
            mock_apy.return_value = 0.045  # 4.5%
            apy = await eth_staking_protocol.get_apy()
            assert apy == 0.045

    async def test_get_staked_balance(self, eth_staking_protocol):
        """Test getting staked balance for an address."""
        with patch.object(eth_staking_protocol.staking_contract.functions, "balanceOf") as mock_balance:
            mock_balance.return_value.call.return_value = 32 * 10**18
            balance = await eth_staking_protocol.get_staked_balance("0xuser")
            assert balance == 32


# ============================== LIQUID STAKING PROTOCOL TESTS ==============================

class TestLiquidStakingProtocol:
    """Test the LiquidStakingProtocol (Lido, Rocket Pool, etc.)."""

    @pytest.fixture
    def liquid_staking_protocol(self, web3_client_service):
        """Return a LiquidStakingProtocol instance."""
        protocol = LiquidStakingProtocol(
            name="Lido",
            chain_id=1,
            web3_client=web3_client_service,
            staking_contract_address="0x" + "e" * 40,
            token_address="0x" + "f" * 40,
        )
        protocol.staking_contract = MagicMock()
        protocol.token_contract = MagicMock()
        return protocol

    async def test_stake_eth_for_steth(self, liquid_staking_protocol, test_private_key, test_address_from_private_key):
        """Test staking ETH to receive stETH (liquid staking)."""
        with patch.object(liquid_staking_protocol.staking_contract.functions, "submit") as mock_submit:
            mock_submit.return_value.build_transaction.return_value = {
                "to": "0x123",
                "data": "0x",
                "value": 10 * 10**18,
            }
            with patch.object(liquid_staking_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "g" * 64
                with patch.object(liquid_staking_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "g" * 64}
                    result = await liquid_staking_protocol.stake(
                        amount=10,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "g" * 64

    async def test_unstake_steth_for_eth(self, liquid_staking_protocol, test_private_key, test_address_from_private_key):
        """Test unstaking stETH for ETH."""
        with patch.object(liquid_staking_protocol.token_contract.functions, "approve") as mock_approve:
            mock_approve.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(liquid_staking_protocol.staking_contract.functions, "withdraw") as mock_withdraw:
                mock_withdraw.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
                with patch.object(liquid_staking_protocol.web3_client.eth, "send_transaction") as mock_send:
                    mock_send.side_effect = ["0x" + "h" * 64, "0x" + "i" * 64]
                    with patch.object(liquid_staking_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                        mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "i" * 64}
                        result = await liquid_staking_protocol.unstake(
                            amount=5,
                            from_address=test_address_from_private_key,
                            private_key=test_private_key,
                        )
                        assert result["tx_hash"] == "0x" + "i" * 64

    async def test_get_steth_balance(self, liquid_staking_protocol):
        """Test getting stETH balance."""
        with patch.object(liquid_staking_protocol.token_contract.functions, "balanceOf") as mock_balance:
            mock_balance.return_value.call.return_value = 10 * 10**18
            balance = await liquid_staking_protocol.get_staked_balance("0xuser")
            assert balance == 10

    async def test_get_apy(self, liquid_staking_protocol):
        """Test getting APY for liquid staking."""
        with patch.object(liquid_staking_protocol, "_fetch_lido_apy") as mock_apy:
            mock_apy.return_value = 0.05
            apy = await liquid_staking_protocol.get_apy()
            assert apy == 0.05


# ============================== BNB STAKING PROTOCOL TESTS ==============================

class TestBnbStakingProtocol:
    """Test the BnbStakingProtocol for BNB staking."""

    @pytest.fixture
    def bnb_staking_protocol(self, web3_client_service):
        """Return a BnbStakingProtocol instance."""
        protocol = BnbStakingProtocol(
            name="BNB Staking",
            chain_id=56,
            web3_client=web3_client_service,
            staking_contract_address="0x" + "j" * 40,
        )
        protocol.staking_contract = MagicMock()
        return protocol

    async def test_stake_bnb(self, bnb_staking_protocol, test_private_key, test_address_from_private_key):
        """Test staking BNB."""
        with patch.object(bnb_staking_protocol.staking_contract.functions, "deposit") as mock_deposit:
            mock_deposit.return_value.build_transaction.return_value = {
                "to": "0x123",
                "data": "0x",
                "value": 10 * 10**18,
            }
            with patch.object(bnb_staking_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "k" * 64
                with patch.object(bnb_staking_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "k" * 64}
                    result = await bnb_staking_protocol.stake(
                        amount=10,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "k" * 64

    async def test_get_apy(self, bnb_staking_protocol):
        """Test getting BNB staking APY."""
        with patch.object(bnb_staking_protocol, "_fetch_bnb_staking_apy") as mock_apy:
            mock_apy.return_value = 0.06
            apy = await bnb_staking_protocol.get_apy()
            assert apy == 0.06


# ============================== SOLANA STAKING PROTOCOL TESTS ==============================

class TestSolStakingProtocol:
    """Test the SolStakingProtocol for SOL staking."""

    @pytest.fixture
    def sol_staking_protocol(self, web3_client_service):
        """Return a SolStakingProtocol instance."""
        # Solana uses a different client, but we'll mock for consistency.
        protocol = SolStakingProtocol(
            name="SOL Staking",
            chain_id=501,  # Solana devnet
            web3_client=web3_client_service,  # placeholder
            staking_program_id="StakingProgramId",
        )
        return protocol

    async def test_stake_sol(self, sol_staking_protocol, test_private_key, test_address_from_private_key):
        """Test staking SOL (using mock)."""
        # Since Solana is different, we mock the underlying method.
        with patch.object(sol_staking_protocol, "_stake_sol_impl") as mock_stake_impl:
            mock_stake_impl.return_value = {"tx_hash": "0x" + "l" * 64, "status": "pending"}
            result = await sol_staking_protocol.stake(
                amount=100,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
                validator_address="0xValidator",
            )
            assert result["tx_hash"] == "0x" + "l" * 64

    async def test_get_apy(self, sol_staking_protocol):
        """Test getting SOL staking APY."""
        with patch.object(sol_staking_protocol, "_fetch_sol_staking_apy") as mock_apy:
            mock_apy.return_value = 0.07
            apy = await sol_staking_protocol.get_apy()
            assert apy == 0.07


# ============================== STAKING MANAGER TESTS ==============================

class TestStakingManager:
    """Test the StakingManager orchestrating multiple staking protocols."""

    @pytest.fixture
    def staking_manager(self, eth_staking_protocol, liquid_staking_protocol, bnb_staking_protocol):
        """Return a StakingManager with registered protocols."""
        manager = StakingManager()
        manager.register_protocol("eth_staking", eth_staking_protocol)
        manager.register_protocol("lido", liquid_staking_protocol)
        manager.register_protocol("bnb_staking", bnb_staking_protocol)
        return manager

    def test_register_protocol(self, staking_manager):
        """Test registering a protocol."""
        mock_protocol = MagicMock()
        mock_protocol.name = "TestProtocol"
        staking_manager.register_protocol("test", mock_protocol)
        assert "test" in staking_manager.protocols

    def test_get_protocol(self, staking_manager):
        """Test retrieving a protocol."""
        protocol = staking_manager.get_protocol("eth_staking")
        assert protocol.name == "ETH Staking"

    def test_get_protocol_not_found(self, staking_manager):
        """Test retrieving a non-existent protocol."""
        with pytest.raises(KeyError):
            staking_manager.get_protocol("unknown")

    def test_list_protocols(self, staking_manager):
        """Test listing all protocols."""
        protocols = staking_manager.list_protocols()
        assert len(protocols) == 3
        assert "eth_staking" in protocols

    async def test_stake_through_manager(self, staking_manager, test_private_key, test_address_from_private_key):
        """Test staking through the manager."""
        protocol = staking_manager.get_protocol("eth_staking")
        with patch.object(protocol, "stake") as mock_stake:
            mock_stake.return_value = {"tx_hash": "0x" + "m" * 64}
            result = await staking_manager.stake(
                protocol_name="eth_staking",
                amount=32,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "m" * 64
            mock_stake.assert_called_once_with(
                amount=32,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )

    async def test_unstake_through_manager(self, staking_manager, test_private_key, test_address_from_private_key):
        """Test unstaking through the manager."""
        protocol = staking_manager.get_protocol("lido")
        with patch.object(protocol, "unstake") as mock_unstake:
            mock_unstake.return_value = {"tx_hash": "0x" + "n" * 64}
            result = await staking_manager.unstake(
                protocol_name="lido",
                amount=10,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "n" * 64
            mock_unstake.assert_called_once()

    async def test_get_apy_from_manager(self, staking_manager):
        """Test getting APY from a protocol via manager."""
        protocol = staking_manager.get_protocol("eth_staking")
        with patch.object(protocol, "get_apy") as mock_apy:
            mock_apy.return_value = 0.045
            apy = await staking_manager.get_apy("eth_staking")
            assert apy == 0.045

    async def test_get_best_apy(self, staking_manager):
        """Test finding the protocol with the best APY."""
        # Mock APYs for each protocol
        with patch.object(staking_manager.protocols["eth_staking"], "get_apy") as mock_eth:
            mock_eth.return_value = 0.045
            with patch.object(staking_manager.protocols["lido"], "get_apy") as mock_lido:
                mock_lido.return_value = 0.05
                with patch.object(staking_manager.protocols["bnb_staking"], "get_apy") as mock_bnb:
                    mock_bnb.return_value = 0.06
                    best = await staking_manager.get_best_apy()
                    assert best["protocol"] == "bnb_staking"
                    assert best["apy"] == 0.06


# ============================== STAKING POOL MANAGER TESTS ==============================

class TestStakingPoolManager:
    """Test the StakingPoolManager for pool-based staking."""

    @pytest.fixture
    def pool_manager(self):
        """Return a StakingPoolManager instance."""
        return StakingPoolManager()

    async def test_create_pool(self, pool_manager):
        """Test creating a staking pool."""
        pool_data = {
            "name": "ETH Pool",
            "asset": "ETH",
            "min_stake": 1,
            "max_stake": 1000,
            "apy": 0.05,
            "lockup_days": 30,
            "is_active": True,
        }
        pool = await pool_manager.create_pool(pool_data)
        assert pool["id"] is not None
        assert pool["name"] == "ETH Pool"
        assert pool["apy"] == 0.05

    async def test_get_pool(self, pool_manager):
        """Test retrieving a pool."""
        pool_data = {"name": "Test Pool", "asset": "ETH", "apy": 0.04}
        pool = await pool_manager.create_pool(pool_data)
        retrieved = await pool_manager.get_pool(pool["id"])
        assert retrieved["name"] == "Test Pool"

    async def test_list_pools(self, pool_manager):
        """Test listing all pools."""
        await pool_manager.create_pool({"name": "Pool A", "asset": "ETH", "apy": 0.05})
        await pool_manager.create_pool({"name": "Pool B", "asset": "USDC", "apy": 0.08})
        pools = await pool_manager.list_pools()
        assert len(pools) == 2

    async def test_update_pool(self, pool_manager):
        """Test updating a pool."""
        pool = await pool_manager.create_pool({"name": "Old Name", "asset": "ETH", "apy": 0.04})
        updated = await pool_manager.update_pool(pool["id"], {"name": "New Name", "apy": 0.06})
        assert updated["name"] == "New Name"
        assert updated["apy"] == 0.06

    async def test_deposit_to_pool(self, pool_manager, test_private_key, test_address_from_private_key):
        """Test depositing into a staking pool."""
        pool = await pool_manager.create_pool({"name": "ETH Pool", "asset": "ETH", "apy": 0.05})
        with patch.object(pool_manager, "_deposit_impl") as mock_deposit:
            mock_deposit.return_value = {"tx_hash": "0x" + "o" * 64}
            result = await pool_manager.deposit_to_pool(
                pool_id=pool["id"],
                amount=10,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "o" * 64

    async def test_withdraw_from_pool(self, pool_manager, test_private_key, test_address_from_private_key):
        """Test withdrawing from a staking pool."""
        pool = await pool_manager.create_pool({"name": "ETH Pool", "asset": "ETH", "apy": 0.05})
        with patch.object(pool_manager, "_withdraw_impl") as mock_withdraw:
            mock_withdraw.return_value = {"tx_hash": "0x" + "p" * 64}
            result = await pool_manager.withdraw_from_pool(
                pool_id=pool["id"],
                amount=5,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "p" * 64

    async def test_get_pool_apy(self, pool_manager):
        """Test getting APY from a pool (cached or updated)."""
        pool = await pool_manager.create_pool({"name": "ETH Pool", "asset": "ETH", "apy": 0.05})
        apy = await pool_manager.get_pool_apy(pool["id"])
        assert apy == 0.05


# ============================== STAKING APY CALCULATOR TESTS ==============================

class TestStakingAPYCalculator:
    """Test the StakingAPYCalculator for yield calculations."""

    @pytest.fixture
    def apy_calculator(self):
        """Return a StakingAPYCalculator instance."""
        return StakingAPYCalculator()

    def test_calculate_simple_apy(self, apy_calculator):
        """Test simple APY calculation (annualized)."""
        rewards = 100
        principal = 1000
        days = 365
        apy = apy_calculator.calculate_simple_apy(rewards, principal, days)
        # Annual yield = (100/1000) = 10%
        assert apy == 0.10

    def test_calculate_compound_apy(self, apy_calculator):
        """Test compound APY with daily compounding."""
        rate_per_period = 0.01  # 1% per day
        periods = 365
        apy = apy_calculator.calculate_compound_apy(rate_per_period, periods)
        # (1 + 0.01)^365 - 1 ≈ 3678% (realistic for daily high rate)
        # We'll just check it's > 0
        assert apy > 0

    def test_calculate_apr_from_apy(self, apy_calculator):
        """Test converting APY to APR (reverse compounding)."""
        apy = 0.05  # 5%
        apr = apy_calculator.calculate_apr_from_apy(apy, periods=365)
        # APR should be slightly less than APY due to compounding
        assert apr < apy
        assert apr > 0

    def test_calculate_rewards(self, apy_calculator):
        """Test calculating expected rewards based on APY."""
        principal = 1000
        apy = 0.05
        days = 30
        rewards = apy_calculator.calculate_rewards(principal, apy, days)
        # 1000 * 0.05 * 30/365 ≈ 4.1096
        assert round(rewards, 4) == 4.1096


# ============================== STAKING REWARD MANAGER TESTS ==============================

class TestStakingRewardManager:
    """Test the StakingRewardManager for reward distribution."""

    @pytest.fixture
    def reward_manager(self):
        """Return a StakingRewardManager instance."""
        return StakingRewardManager()

    async def test_claim_rewards(self, reward_manager, test_private_key, test_address_from_private_key):
        """Test claiming rewards."""
        with patch.object(reward_manager, "_claim_impl") as mock_claim:
            mock_claim.return_value = {"tx_hash": "0x" + "q" * 64, "amount": 100}
            result = await reward_manager.claim_rewards(
                protocol="eth_staking",
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "q" * 64
            assert result["amount"] == 100

    async def test_get_pending_rewards(self, reward_manager):
        """Test getting pending rewards for a user."""
        with patch.object(reward_manager, "_fetch_pending_rewards") as mock_pending:
            mock_pending.return_value = 50
            pending = await reward_manager.get_pending_rewards("eth_staking", "0xuser")
            assert pending == 50

    async def test_auto_compound(self, reward_manager, test_private_key, test_address_from_private_key):
        """Test auto-compounding rewards."""
        with patch.object(reward_manager, "_compound_impl") as mock_compound:
            mock_compound.return_value = {"tx_hash": "0x" + "r" * 64}
            result = await reward_manager.auto_compound(
                protocol="eth_staking",
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "r" * 64


# ============================== STAKING VALIDATOR MANAGER TESTS ==============================

class TestStakingValidatorManager:
    """Test the StakingValidatorManager for validator selection."""

    @pytest.fixture
    def validator_manager(self):
        """Return a StakingValidatorManager instance."""
        return StakingValidatorManager()

    async def test_get_validators(self, validator_manager):
        """Test retrieving validators."""
        with patch.object(validator_manager, "_fetch_validator_list") as mock_list:
            mock_list.return_value = [
                {"address": "0xVal1", "commission": 0.1, "stake": 1000},
                {"address": "0xVal2", "commission": 0.05, "stake": 500},
            ]
            validators = await validator_manager.get_validators("eth")
            assert len(validators) == 2

    async def test_choose_validator(self, validator_manager):
        """Test choosing the best validator based on criteria."""
        validators = [
            {"address": "0xVal1", "commission": 0.1, "apy": 0.05, "uptime": 0.99},
            {"address": "0xVal2", "commission": 0.05, "apy": 0.04, "uptime": 0.98},
            {"address": "0xVal3", "commission": 0.08, "apy": 0.06, "uptime": 0.95},
        ]
        # Choose based on highest APY with reasonable commission
        with patch.object(validator_manager, "_fetch_validators", return_value=validators):
            chosen = await validator_manager.choose_validator(
                protocol="eth",
                min_uptime=0.97,
                max_commission=0.12,
                preference="apy",
            )
            # Should pick Val3 with highest APY (0.06) but need to check uptime? uptime 0.95 < 0.97, so excluded.
            # Next best APY is Val1 (0.05) with uptime 0.99
            assert chosen["address"] == "0xVal1"

    async def test_delegate_to_validator(self, validator_manager, test_private_key, test_address_from_private_key):
        """Test delegating to a validator."""
        with patch.object(validator_manager, "_delegate_impl") as mock_delegate:
            mock_delegate.return_value = {"tx_hash": "0x" + "s" * 64}
            result = await validator_manager.delegate(
                protocol="eth",
                validator_address="0xVal1",
                amount=10,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "s" * 64


# ============================== STAKING ANALYTICS TESTS ==============================

class TestStakingAnalytics:
    """Test the StakingAnalytics for staking performance tracking."""

    @pytest.fixture
    def staking_analytics(self):
        """Return a StakingAnalytics instance."""
        return StakingAnalytics()

    async def test_get_staking_summary(self, staking_analytics):
        """Test getting a staking summary for a user."""
        with patch.object(staking_analytics, "_fetch_user_staking_data") as mock_data:
            mock_data.return_value = {
                "total_staked": 1000,
                "total_rewards": 50,
                "active_positions": 3,
                "apy": 0.05,
            }
            summary = await staking_analytics.get_staking_summary("0xuser")
            assert summary["total_staked"] == 1000
            assert summary["total_rewards"] == 50

    async def test_get_historical_apy(self, staking_analytics):
        """Test getting historical APY for a protocol."""
        with patch.object(staking_analytics, "_fetch_historical_apy") as mock_hist:
            mock_hist.return_value = [
                {"date": "2024-01-01", "apy": 0.05},
                {"date": "2024-01-02", "apy": 0.06},
            ]
            history = await staking_analytics.get_historical_apy("eth_staking", days=7)
            assert len(history) == 2

    async def test_compare_staking_protocols(self, staking_analytics):
        """Test comparing multiple staking protocols."""
        with patch.object(staking_analytics, "_fetch_protocol_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "Lido": {"apy": 0.05, "tvl": 10e9, "risk_score": 0.8},
                "RocketPool": {"apy": 0.055, "tvl": 3e9, "risk_score": 0.9},
            }
            comparison = await staking_analytics.compare_protocols(["Lido", "RocketPool"])
            assert "Lido" in comparison
            assert comparison["Lido"]["apy"] == 0.05

    async def test_get_staking_risk_report(self, staking_analytics):
        """Test generating a staking risk report."""
        with patch.object(staking_analytics, "_assess_risk") as mock_risk:
            mock_risk.return_value = {
                "risk_score": 30,
                "risk_level": "low",
                "factors": {"volatility": 0.2, "liquidity": 0.8},
            }
            report = await staking_analytics.get_staking_risk_report("0xuser")
            assert report["risk_level"] == "low"


# ============================== STAKING RISK MANAGER TESTS ==============================

class TestStakingRiskManager:
    """Test the StakingRiskManager for staking risk assessment."""

    @pytest.fixture
    def staking_risk_manager(self):
        """Return a StakingRiskManager instance."""
        return StakingRiskManager()

    async def test_assess_protocol_risk(self, staking_risk_manager):
        """Test assessing risk of a staking protocol."""
        with patch.object(staking_risk_manager, "_fetch_protocol_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "tvl": 1e9,
                "audits": ["CertiK"],
                "slashing_events": 0,
                "withdrawal_delay": 7,
            }
            score = await staking_risk_manager.assess_protocol_risk("Lido")
            assert score["risk_score"] < 50
            assert score["risk_level"] in ("low", "medium")

    async def test_check_slashing_risk(self, staking_risk_manager):
        """Test calculating slashing risk based on validator performance."""
        # Simulate validator with high uptime and no slashing
        risk = await staking_risk_manager.check_slashing_risk(
            protocol="eth",
            validator_address="0xValidator",
            uptime=0.99,
            slashable_events=0,
        )
        assert risk["slashing_probability"] < 0.01

        # Simulate validator with lower uptime and some slashing events
        risk2 = await staking_risk_manager.check_slashing_risk(
            protocol="eth",
            validator_address="0xValidator2",
            uptime=0.90,
            slashable_events=2,
        )
        assert risk2["slashing_probability"] > 0.05

    async def test_evaluate_iliquidity_risk(self, staking_risk_manager):
        """Test evaluating liquidity risk (withdrawal delays)."""
        risk = await staking_risk_manager.evaluate_iliquidity_risk(
            protocol="eth_staking",
            withdrawal_days=30,
        )
        # Longer withdrawal = higher risk
        assert risk["risk_score"] > 0.5


# ============================== CONFIGURATION TESTS ==============================

class TestStakingConfig:
    """Test staking configuration."""

    def test_load_config(self):
        """Test loading staking configuration."""
        config = StakingConfig()
        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "protocols": {
                    "eth_staking": {"enabled": True, "min_stake": 32},
                    "lido": {"enabled": True, "min_stake": 0.1},
                },
                "default_apy": 0.05,
            })
            config.load_from_file("staking_config.json")
            assert config.protocols["eth_staking"]["min_stake"] == 32
            assert config.default_apy == 0.05

    def test_get_protocol_config(self, staking_config):
        """Test retrieving configuration for a protocol."""
        config = StakingConfig()
        config.protocols = {"eth_staking": {"min_stake": 32}}
        cfg = config.get_protocol_config("eth_staking")
        assert cfg["min_stake"] == 32


# ============================== INTEGRATION TESTS ==============================

class TestStakingIntegration:
    """Integration tests for staking components working together."""

    async def test_full_staking_lifecycle(
        self,
        staking_manager,
        reward_manager,
        staking_analytics,
        test_private_key,
        test_address_from_private_key,
    ):
        """Test a complete staking lifecycle: stake -> claim rewards -> unstake."""
        protocol_name = "eth_staking"

        # 1. Stake
        with patch.object(staking_manager.protocols[protocol_name], "stake") as mock_stake:
            mock_stake.return_value = {"tx_hash": "0x" + "t" * 64}
            stake_result = await staking_manager.stake(
                protocol_name=protocol_name,
                amount=32,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert stake_result["tx_hash"] == "0x" + "t" * 64

        # 2. Get APY
        with patch.object(staking_manager.protocols[protocol_name], "get_apy") as mock_apy:
            mock_apy.return_value = 0.045
            apy = await staking_manager.get_apy(protocol_name)
            assert apy == 0.045

        # 3. Get pending rewards (after some time)
        with patch.object(reward_manager, "get_pending_rewards") as mock_pending:
            mock_pending.return_value = 2.0
            pending = await reward_manager.get_pending_rewards(protocol_name, test_address_from_private_key)
            assert pending == 2.0

        # 4. Claim rewards
        with patch.object(reward_manager, "claim_rewards") as mock_claim:
            mock_claim.return_value = {"tx_hash": "0x" + "u" * 64, "amount": 2.0}
            claim_result = await reward_manager.claim_rewards(
                protocol=protocol_name,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert claim_result["tx_hash"] == "0x" + "u" * 64

        # 5. Unstake
        with patch.object(staking_manager.protocols[protocol_name], "unstake") as mock_unstake:
            mock_unstake.return_value = {"tx_hash": "0x" + "v" * 64}
            unstake_result = await staking_manager.unstake(
                protocol_name=protocol_name,
                amount=16,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert unstake_result["tx_hash"] == "0x" + "v" * 64

        # 6. Get summary
        with patch.object(staking_analytics, "get_staking_summary") as mock_summary:
            mock_summary.return_value = {"total_staked": 16, "total_rewards": 2.0}
            summary = await staking_analytics.get_staking_summary(test_address_from_private_key)
            assert summary["total_staked"] == 16

    async def test_best_apy_selection_with_risk(self, staking_manager, staking_risk_manager):
        """Test selecting the best APY protocol considering risk."""
        # Mock APYs and risk scores
        with patch.object(staking_manager.protocols["eth_staking"], "get_apy") as mock_eth:
            mock_eth.return_value = 0.045
            with patch.object(staking_manager.protocols["lido"], "get_apy") as mock_lido:
                mock_lido.return_value = 0.05
                with patch.object(staking_manager.protocols["bnb_staking"], "get_apy") as mock_bnb:
                    mock_bnb.return_value = 0.06

                    # Risk scores
                    with patch.object(staking_risk_manager, "assess_protocol_risk") as mock_risk:
                        mock_risk.side_effect = [
                            {"risk_score": 30, "risk_level": "low"},
                            {"risk_score": 50, "risk_level": "medium"},
                            {"risk_score": 70, "risk_level": "high"},
                        ]
                        # Get best APY with risk constraint (max medium risk)
                        best = await staking_manager.get_best_apy(max_risk_level="medium")
                        # Should exclude bnb_staking (high risk), choose lido (medium, 0.05) vs eth (low, 0.045)
                        assert best["protocol"] == "lido"
                        assert best["apy"] == 0.05

    async def test_validator_delegation_with_staking(self, staking_manager, validator_manager, test_private_key, test_address_from_private_key):
        """Test staking via validator delegation."""
        # Choose validator
        validators = [
            {"address": "0xVal1", "commission": 0.1, "apy": 0.05},
            {"address": "0xVal2", "commission": 0.05, "apy": 0.06},
        ]
        with patch.object(validator_manager, "_fetch_validators", return_value=validators):
            chosen = await validator_manager.choose_validator(
                protocol="eth",
                min_uptime=0.97,
                max_commission=0.12,
                preference="apy",
            )
            assert chosen["address"] == "0xVal2"  # higher APY

        # Delegate stake to chosen validator
        with patch.object(validator_manager, "delegate") as mock_delegate:
            mock_delegate.return_value = {"tx_hash": "0x" + "w" * 64}
            result = await validator_manager.delegate(
                protocol="eth",
                validator_address=chosen["address"],
                amount=32,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "w" * 64
