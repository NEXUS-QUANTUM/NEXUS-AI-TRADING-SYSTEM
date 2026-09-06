# tests/blockchain/test_defi_protocols.py
"""
DeFi Protocol Tests for the NEXUS AI Trading System.

This module contains comprehensive tests for all DeFi protocol integrations:
- Aave (lending, borrowing, flash loans)
- Uniswap (swapping, liquidity provision)
- Compound (supply, borrow)
- Curve (stable swaps, staking)
- Lido (ETH staking)
- PancakeSwap (BSC swaps)
- Balancer (weighted pools)
- 1inch (aggregator)
- DeFi analytics and risk assessment

All tests use mocked contract interactions to ensure fast and reliable test execution.
"""

import asyncio
from decimal import Decimal
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockchain.defi.base_protocol import BaseDeFiProtocol
from blockchain.defi.defi_manager import DeFiManager
from blockchain.defi.aave import AaveProtocol
from blockchain.defi.uniswap import UniswapProtocol
from blockchain.defi.compound import CompoundProtocol
from blockchain.defi.curve import CurveProtocol
from blockchain.defi.lido import LidoProtocol
from blockchain.defi.pancake_swap import PancakeSwapProtocol
from blockchain.defi.balancer import BalancerProtocol
from blockchain.defi.defi_aggregator import DeFiAggregator
from blockchain.defi.defi_analytics import DeFiAnalytics
from blockchain.defi.defi_risk import DeFiRiskManager
from blockchain.defi.flash_loan import FlashLoanManager
from blockchain.defi.yield_farming import YieldFarmingManager
from blockchain.defi.lending import LendingManager
from blockchain.defi.staking import StakingProtocol
from blockchain.defi.defi_config import DeFiConfig

pytest_plugins = ["tests.blockchain.conftest"]


# ============================== BASE PROTOCOL TESTS ==============================

class TestBaseDeFiProtocol:
    """Test the BaseDeFiProtocol abstract class."""

    def test_base_protocol_initialization(self):
        """Test initializing a base DeFi protocol."""
        protocol = BaseDeFiProtocol(name="TestProtocol", chain_id=1)
        assert protocol.name == "TestProtocol"
        assert protocol.chain_id == 1
        assert protocol.is_active is True

    async def test_get_apy_not_implemented(self):
        """Test that get_apy raises NotImplementedError."""
        protocol = BaseDeFiProtocol(name="Test", chain_id=1)
        with pytest.raises(NotImplementedError):
            await protocol.get_apy()

    async def test_get_liquidity_not_implemented(self):
        """Test that get_liquidity raises NotImplementedError."""
        protocol = BaseDeFiProtocol(name="Test", chain_id=1)
        with pytest.raises(NotImplementedError):
            await protocol.get_liquidity()

    def test_get_protocol_info(self):
        """Test retrieving protocol information."""
        protocol = BaseDeFiProtocol(name="Test", chain_id=1)
        info = protocol.get_protocol_info()
        assert info["name"] == "Test"
        assert info["chain_id"] == 1
        assert "supported_tokens" in info


# ============================== AAVE PROTOCOL TESTS ==============================

class TestAaveProtocol:
    """Test the Aave protocol integration."""

    @pytest.fixture
    def aave_protocol(self, web3_client_service, mock_aave_contract):
        """Return an AaveProtocol instance with mocked contract."""
        protocol = AaveProtocol(
            name="Aave",
            chain_id=1,
            web3_client=web3_client_service,
            lending_pool_address="0x" + "a" * 40,
        )
        protocol.lending_pool = mock_aave_contract
        return protocol

    async def test_deposit(self, aave_protocol, test_private_key, test_address_from_private_key):
        """Test depositing assets into Aave."""
        with patch.object(aave_protocol.lending_pool.functions, "deposit") as mock_deposit:
            mock_deposit.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(aave_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "a" * 64
                with patch.object(aave_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "a" * 64}
                    result = await aave_protocol.deposit(
                        asset="0xUSDC",
                        amount=1000,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "a" * 64
                    assert result["status"] == "completed"
                    mock_deposit.assert_called_once()

    async def test_withdraw(self, aave_protocol, test_private_key, test_address_from_private_key):
        """Test withdrawing assets from Aave."""
        with patch.object(aave_protocol.lending_pool.functions, "withdraw") as mock_withdraw:
            mock_withdraw.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(aave_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "b" * 64
                with patch.object(aave_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "b" * 64}
                    result = await aave_protocol.withdraw(
                        asset="0xUSDC",
                        amount=500,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "b" * 64

    async def test_borrow(self, aave_protocol, test_private_key, test_address_from_private_key):
        """Test borrowing assets from Aave."""
        with patch.object(aave_protocol.lending_pool.functions, "borrow") as mock_borrow:
            mock_borrow.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(aave_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "c" * 64
                with patch.object(aave_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "c" * 64}
                    result = await aave_protocol.borrow(
                        asset="0xWETH",
                        amount=10,
                        interest_rate_mode=2,  # variable
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "c" * 64

    async def test_repay(self, aave_protocol, test_private_key, test_address_from_private_key):
        """Test repaying borrowed assets."""
        with patch.object(aave_protocol.lending_pool.functions, "repay") as mock_repay:
            mock_repay.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(aave_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "d" * 64
                with patch.object(aave_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "d" * 64}
                    result = await aave_protocol.repay(
                        asset="0xWETH",
                        amount=5,
                        interest_rate_mode=2,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "d" * 64

    async def test_get_apy(self, aave_protocol):
        """Test getting APY from Aave."""
        with patch.object(aave_protocol.lending_pool.functions, "getReserveData") as mock_reserve:
            mock_reserve.return_value.call.return_value = (0, 0.05, 0.01, 0.02, 0, 0, 0)
            apy = await aave_protocol.get_apy(asset="0xUSDC")
            assert apy["deposit_apy"] == 0.05
            assert apy["borrow_apy"] == 0.02

    async def test_get_liquidity(self, aave_protocol):
        """Test getting liquidity from Aave."""
        with patch.object(aave_protocol.lending_pool.functions, "getReserveData") as mock_reserve:
            mock_reserve.return_value.call.return_value = (1000000, 0.05, 0.01, 0.02, 0, 0, 0)
            liquidity = await aave_protocol.get_liquidity(asset="0xUSDC")
            assert liquidity["available_liquidity"] == 1000000


# ============================== UNISWAP PROTOCOL TESTS ==============================

class TestUniswapProtocol:
    """Test the Uniswap protocol integration (V2/V3)."""

    @pytest.fixture
    def uniswap_protocol(self, web3_client_service, mock_uniswap_contract):
        """Return a UniswapProtocol instance."""
        protocol = UniswapProtocol(
            name="Uniswap V3",
            chain_id=1,
            web3_client=web3_client_service,
            router_address="0x" + "b" * 40,
        )
        protocol.router = mock_uniswap_contract
        return protocol

    async def test_swap_exact_tokens_for_tokens(self, uniswap_protocol, test_private_key, test_address_from_private_key):
        """Test swapping exact tokens for tokens."""
        with patch.object(uniswap_protocol.router.functions, "swapExactTokensForTokens") as mock_swap:
            mock_swap.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(uniswap_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "e" * 64
                with patch.object(uniswap_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "e" * 64}
                    result = await uniswap_protocol.swap(
                        token_in="0xUSDC",
                        token_out="0xWETH",
                        amount_in=1000,
                        min_amount_out=0.9,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "e" * 64

    async def test_swap_eth_for_tokens(self, uniswap_protocol, test_private_key, test_address_from_private_key):
        """Test swapping ETH for tokens."""
        with patch.object(uniswap_protocol.router.functions, "swapExactETHForTokens") as mock_swap:
            mock_swap.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(uniswap_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "f" * 64
                with patch.object(uniswap_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "f" * 64}
                    result = await uniswap_protocol.swap_eth_for_tokens(
                        token_out="0xUSDC",
                        amount_eth=1.0,
                        min_tokens=1000,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "f" * 64

    async def test_add_liquidity(self, uniswap_protocol, test_private_key, test_address_from_private_key):
        """Test adding liquidity to a pool."""
        with patch.object(uniswap_protocol.router.functions, "addLiquidity") as mock_add:
            mock_add.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(uniswap_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "g" * 64
                with patch.object(uniswap_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "g" * 64}
                    result = await uniswap_protocol.add_liquidity(
                        token_a="0xUSDC",
                        token_b="0xWETH",
                        amount_a=1000,
                        amount_b=1.0,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "g" * 64

    async def test_remove_liquidity(self, uniswap_protocol, test_private_key, test_address_from_private_key):
        """Test removing liquidity from a pool."""
        with patch.object(uniswap_protocol.router.functions, "removeLiquidity") as mock_remove:
            mock_remove.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(uniswap_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "h" * 64
                with patch.object(uniswap_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "h" * 64}
                    result = await uniswap_protocol.remove_liquidity(
                        token_a="0xUSDC",
                        token_b="0xWETH",
                        liquidity=100,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "h" * 64

    async def test_get_swap_quote(self, uniswap_protocol):
        """Test getting a swap quote."""
        with patch.object(uniswap_protocol.router.functions, "getAmountsOut") as mock_quote:
            mock_quote.return_value.call.return_value = [1000, 2000]
            quote = await uniswap_protocol.get_swap_quote(
                token_in="0xUSDC",
                token_out="0xWETH",
                amount_in=1000,
            )
            assert quote["amount_out"] == 2000
            assert quote["price_impact"] is not None


# ============================== COMPOUND PROTOCOL TESTS ==============================

class TestCompoundProtocol:
    """Test the Compound protocol integration."""

    @pytest.fixture
    def compound_protocol(self, web3_client_service):
        """Return a CompoundProtocol instance."""
        protocol = CompoundProtocol(
            name="Compound",
            chain_id=1,
            web3_client=web3_client_service,
            comptroller_address="0x" + "c" * 40,
            ctoken_addresses={"USDC": "0x" + "d" * 40},
        )
        # Mock the cToken contract
        protocol.ctoken = MagicMock()
        return protocol

    async def test_supply(self, compound_protocol, test_private_key, test_address_from_private_key):
        """Test supplying assets to Compound."""
        with patch.object(compound_protocol.ctoken.functions, "mint") as mock_mint:
            mock_mint.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(compound_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "i" * 64
                with patch.object(compound_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "i" * 64}
                    result = await compound_protocol.supply(
                        asset="USDC",
                        amount=1000,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "i" * 64

    async def test_redeem(self, compound_protocol, test_private_key, test_address_from_private_key):
        """Test redeeming assets from Compound."""
        with patch.object(compound_protocol.ctoken.functions, "redeem") as mock_redeem:
            mock_redeem.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(compound_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "j" * 64
                with patch.object(compound_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "j" * 64}
                    result = await compound_protocol.redeem(
                        asset="USDC",
                        amount=500,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "j" * 64

    async def test_get_supply_apy(self, compound_protocol):
        """Test getting supply APY from Compound."""
        with patch.object(compound_protocol, "_get_ctoken_info") as mock_info:
            mock_info.return_value = {"supply_apy": 0.04, "borrow_apy": 0.02}
            apy = await compound_protocol.get_apy(asset="USDC")
            assert apy["supply_apy"] == 0.04


# ============================== CURVE PROTOCOL TESTS ==============================

class TestCurveProtocol:
    """Test the Curve protocol integration (stable swaps)."""

    @pytest.fixture
    def curve_protocol(self, web3_client_service):
        """Return a CurveProtocol instance."""
        protocol = CurveProtocol(
            name="Curve",
            chain_id=1,
            web3_client=web3_client_service,
            pool_address="0x" + "e" * 40,
        )
        protocol.pool = MagicMock()
        return protocol

    async def test_swap(self, curve_protocol, test_private_key, test_address_from_private_key):
        """Test swapping stablecoins on Curve."""
        with patch.object(curve_protocol.pool.functions, "exchange") as mock_exchange:
            mock_exchange.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(curve_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "k" * 64
                with patch.object(curve_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "k" * 64}
                    result = await curve_protocol.swap(
                        from_token="0xUSDC",
                        to_token="0xDAI",
                        amount=1000,
                        min_amount=999,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "k" * 64

    async def test_add_liquidity(self, curve_protocol, test_private_key, test_address_from_private_key):
        """Test adding liquidity to Curve pool."""
        with patch.object(curve_protocol.pool.functions, "add_liquidity") as mock_add:
            mock_add.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(curve_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "l" * 64
                with patch.object(curve_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "l" * 64}
                    result = await curve_protocol.add_liquidity(
                        amounts=[1000, 1000],
                        min_mint=0,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "l" * 64


# ============================== LIDO PROTOCOL TESTS ==============================

class TestLidoProtocol:
    """Test the Lido protocol integration (staking)."""

    @pytest.fixture
    def lido_protocol(self, web3_client_service):
        """Return a LidoProtocol instance."""
        protocol = LidoProtocol(
            name="Lido",
            chain_id=1,
            web3_client=web3_client_service,
            staking_address="0x" + "f" * 40,
        )
        protocol.staking = MagicMock()
        return protocol

    async def test_stake_eth(self, lido_protocol, test_private_key, test_address_from_private_key):
        """Test staking ETH to receive stETH."""
        with patch.object(lido_protocol.staking.functions, "submit") as mock_submit:
            mock_submit.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(lido_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "m" * 64
                with patch.object(lido_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "m" * 64}
                    result = await lido_protocol.stake(
                        amount=32,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "m" * 64

    async def test_get_apy(self, lido_protocol):
        """Test getting staking APY from Lido."""
        with patch.object(lido_protocol, "_get_steth_apy") as mock_apy:
            mock_apy.return_value = 0.045
            apy = await lido_protocol.get_apy()
            assert apy["staking_apy"] == 0.045


# ============================== PANCAKESWAP PROTOCOL TESTS ==============================

class TestPancakeSwapProtocol:
    """Test the PancakeSwap protocol integration (BSC)."""

    @pytest.fixture
    def pancakeswap_protocol(self, web3_client_service):
        """Return a PancakeSwapProtocol instance."""
        protocol = PancakeSwapProtocol(
            name="PancakeSwap",
            chain_id=56,
            web3_client=web3_client_service,
            router_address="0x" + "g" * 40,
        )
        protocol.router = MagicMock()
        return protocol

    async def test_swap_bnb_for_tokens(self, pancakeswap_protocol, test_private_key, test_address_from_private_key):
        """Test swapping BNB for tokens on PancakeSwap."""
        with patch.object(pancakeswap_protocol.router.functions, "swapExactBNBForTokens") as mock_swap:
            mock_swap.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(pancakeswap_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "n" * 64
                with patch.object(pancakeswap_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "n" * 64}
                    result = await pancakeswap_protocol.swap_bnb_for_tokens(
                        token_out="0xCAKE",
                        amount_bnb=10,
                        min_tokens=100,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "n" * 64


# ============================== BALANCER PROTOCOL TESTS ==============================

class TestBalancerProtocol:
    """Test the Balancer protocol integration."""

    @pytest.fixture
    def balancer_protocol(self, web3_client_service):
        """Return a BalancerProtocol instance."""
        protocol = BalancerProtocol(
            name="Balancer",
            chain_id=1,
            web3_client=web3_client_service,
            vault_address="0x" + "h" * 40,
        )
        protocol.vault = MagicMock()
        return protocol

    async def test_swap(self, balancer_protocol, test_private_key, test_address_from_private_key):
        """Test swapping on Balancer."""
        with patch.object(balancer_protocol.vault.functions, "swap") as mock_swap:
            mock_swap.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(balancer_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "o" * 64
                with patch.object(balancer_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "o" * 64}
                    result = await balancer_protocol.swap(
                        pool_id="0xpool",
                        token_in="0xUSDC",
                        token_out="0xWETH",
                        amount_in=1000,
                        min_amount_out=0.9,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "o" * 64


# ============================== DEFI MANAGER TESTS ==============================

class TestDeFiManager:
    """Test the DeFiManager orchestrating multiple protocols."""

    @pytest.fixture
    def defi_manager(self, aave_protocol, uniswap_protocol):
        """Return a DeFiManager with registered protocols."""
        manager = DeFiManager()
        manager.register_protocol("aave", aave_protocol)
        manager.register_protocol("uniswap", uniswap_protocol)
        return manager

    def test_register_protocol(self, defi_manager):
        """Test registering a protocol."""
        mock_protocol = MagicMock()
        defi_manager.register_protocol("curve", mock_protocol)
        assert "curve" in defi_manager.protocols

    def test_get_protocol(self, defi_manager):
        """Test retrieving a protocol."""
        protocol = defi_manager.get_protocol("aave")
        assert protocol.name == "Aave"

    async def test_get_best_swap_route(self, defi_manager):
        """Test finding the best swap route across protocols."""
        # Mock get_swap_quote for each protocol
        with patch.object(defi_manager.protocols["uniswap"], "get_swap_quote") as mock_quote:
            mock_quote.return_value = {"amount_out": 2000, "price_impact": 0.001}
            best = await defi_manager.get_best_swap_route(
                token_in="0xUSDC",
                token_out="0xWETH",
                amount_in=1000,
            )
            assert best["protocol"] == "uniswap"
            assert best["amount_out"] == 2000

    async def test_get_best_apy(self, defi_manager):
        """Test finding the best APY across protocols."""
        with patch.object(defi_manager.protocols["aave"], "get_apy") as mock_aave:
            mock_aave.return_value = {"deposit_apy": 0.05}
            with patch.object(defi_manager.protocols["uniswap"], "get_apy") as mock_uni:
                mock_uni.return_value = {"pool_apy": 0.03}
                best = await defi_manager.get_best_apy(asset="USDC")
                # Should return Aave because 0.05 > 0.03
                assert best["protocol"] == "aave"
                assert best["apy"] == 0.05


# ============================== DEFI AGGREGATOR TESTS ==============================

class TestDeFiAggregator:
    """Test the DeFiAggregator for cross-protocol optimization."""

    @pytest.fixture
    def defi_aggregator(self):
        """Return a DeFiAggregator instance."""
        return DeFiAggregator()

    async def test_find_best_yield(self, defi_aggregator):
        """Test finding the best yield opportunity."""
        # Mock multiple protocol APYs
        mock_protocols = [
            {"name": "Aave", "apy": 0.05, "asset": "USDC", "protocol": "aave"},
            {"name": "Compound", "apy": 0.04, "asset": "USDC", "protocol": "compound"},
            {"name": "Curve", "apy": 0.06, "asset": "USDC", "protocol": "curve"},
        ]
        with patch.object(defi_aggregator, "_fetch_protocol_apys", return_value=mock_protocols):
            best = await defi_aggregator.find_best_yield(asset="USDC")
            assert best["name"] == "Curve"
            assert best["apy"] == 0.06

    async def test_aggregate_swap(self, defi_aggregator):
        """Test aggregating a swap across multiple protocols to optimize price."""
        # Simulate splitting a swap across protocols
        routes = [
            {"protocol": "Uniswap", "amount": 500, "output": 1000},
            {"protocol": "Sushiswap", "amount": 500, "output": 980},
        ]
        with patch.object(defi_aggregator, "_get_optimal_routes", return_value=routes):
            result = await defi_aggregator.aggregate_swap(
                token_in="USDC",
                token_out="WETH",
                amount_in=1000,
            )
            assert len(result["routes"]) == 2
            assert result["total_output"] == 1980


# ============================== DEFI ANALYTICS TESTS ==============================

class TestDeFiAnalytics:
    """Test the DeFiAnalytics module for protocol analytics."""

    @pytest.fixture
    def defi_analytics(self):
        """Return a DeFiAnalytics instance."""
        return DeFiAnalytics()

    async def test_get_protocol_tvl(self, defi_analytics):
        """Test getting TVL for a protocol."""
        with patch.object(defi_analytics, "_fetch_tvl") as mock_tvl:
            mock_tvl.return_value = {"aave": 10e9, "compound": 8e9}
            tvl = await defi_analytics.get_protocol_tvl("aave")
            assert tvl == 10e9

    async def test_get_historical_apy(self, defi_analytics):
        """Test fetching historical APY data."""
        with patch.object(defi_analytics, "_fetch_historical_apy") as mock_hist:
            mock_hist.return_value = [{"date": "2024-01-01", "apy": 0.05}, {"date": "2024-01-02", "apy": 0.06}]
            data = await defi_analytics.get_historical_apy("aave", "USDC", days=30)
            assert len(data) == 2

    async def test_compare_protocols(self, defi_analytics):
        """Test comparing multiple protocols."""
        with patch.object(defi_analytics, "_fetch_protocol_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "Aave": {"tvl": 10e9, "apy": 0.05, "risk_score": 0.8},
                "Compound": {"tvl": 8e9, "apy": 0.04, "risk_score": 0.9},
            }
            comparison = await defi_analytics.compare_protocols(["Aave", "Compound"])
            assert "Aave" in comparison
            assert comparison["Aave"]["apy"] == 0.05


# ============================== DEFI RISK MANAGER TESTS ==============================

class TestDeFiRiskManager:
    """Test the DeFiRiskManager for risk assessment."""

    @pytest.fixture
    def defi_risk_manager(self):
        """Return a DeFiRiskManager instance."""
        return DeFiRiskManager()

    async def test_assess_protocol_risk(self, defi_risk_manager):
        """Test assessing risk of a protocol."""
        with patch.object(defi_risk_manager, "_get_protocol_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "liquidity": 1e6,
                "audits": ["CertiK"],
                "age_days": 365,
                "hack_incidents": 0,
            }
            score = await defi_risk_manager.assess_protocol_risk("Aave")
            assert score["risk_score"] >= 0
            assert score["risk_level"] in ("low", "medium", "high")

    async def test_check_loan_to_value(self, defi_risk_manager):
        """Test checking LTV and liquidation risk."""
        # For a position with 1000 USDC supplied, 500 USDC borrowed, LTV = 50%
        ltv = await defi_risk_manager.check_loan_to_value(
            collateral=1000,
            debt=500,
            collateral_asset="USDC",
            debt_asset="USDC",
            liquidation_threshold=0.8,
        )
        assert ltv["ltv"] == 0.5
        assert ltv["safe"] is True

    async def test_check_liquidation_risk(self, defi_risk_manager):
        """Test calculating liquidation risk based on price movements."""
        # Simulate a 20% drop in collateral price
        risk = await defi_risk_manager.check_liquidation_risk(
            collateral_amount=1000,
            collateral_price=100,
            debt_amount=500,
            debt_price=1,
            liquidation_threshold=0.8,
            price_change=-0.2,
        )
        # If price drops 20%, collateral value becomes 800, LTV = 500/800 = 0.625, still safe
        assert risk["liquidated"] is False
        # If price drops 40%, collateral value 600, LTV = 500/600 = 0.833 > 0.8, liquidated
        risk2 = await defi_risk_manager.check_liquidation_risk(
            collateral_amount=1000,
            collateral_price=100,
            debt_amount=500,
            debt_price=1,
            liquidation_threshold=0.8,
            price_change=-0.5,
        )
        assert risk2["liquidated"] is True


# ============================== FLASH LOAN TESTS ==============================

class TestFlashLoanManager:
    """Test the FlashLoanManager for flash loan operations."""

    @pytest.fixture
    def flash_loan_manager(self, defi_manager):
        """Return a FlashLoanManager instance with DeFiManager."""
        return FlashLoanManager(defi_manager)

    async def test_request_flash_loan(self, flash_loan_manager, test_private_key, test_address_from_private_key):
        """Test requesting a flash loan from Aave."""
        with patch.object(flash_loan_manager.defi_manager.get_protocol("aave"), "flash_loan") as mock_flash:
            mock_flash.return_value = {"tx_hash": "0x" + "p" * 64, "status": "completed"}
            result = await flash_loan_manager.request_flash_loan(
                protocol="aave",
                asset="USDC",
                amount=10000,
                callback_data={"strategy": "arbitrage"},
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "p" * 64

    async def test_flash_loan_arbitrage(self, flash_loan_manager):
        """Test executing a flash loan arbitrage strategy."""
        # Mock the arbitrage strategy
        with patch.object(flash_loan_manager, "_execute_arbitrage") as mock_arb:
            mock_arb.return_value = {"profit": 100}
            result = await flash_loan_manager.execute_arbitrage(
                token_in="USDC",
                token_out="WETH",
                amount=10000,
                from_address="0xfrom",
                private_key="0xkey",
            )
            assert result["profit"] == 100


# ============================== YIELD FARMING TESTS ==============================

class TestYieldFarmingManager:
    """Test the YieldFarmingManager for yield farming strategies."""

    @pytest.fixture
    def yield_farming_manager(self):
        """Return a YieldFarmingManager instance."""
        return YieldFarmingManager()

    async def test_get_farming_opportunities(self, yield_farming_manager):
        """Test fetching yield farming opportunities."""
        with patch.object(yield_farming_manager, "_fetch_pools") as mock_pools:
            mock_pools.return_value = [
                {"pool": "ETH-USDC", "apy": 0.5, "tvl": 1e6, "protocol": "Uniswap"},
                {"pool": "BTC-ETH", "apy": 0.3, "tvl": 2e6, "protocol": "SushiSwap"},
            ]
            opportunities = await yield_farming_manager.get_opportunities()
            assert len(opportunities) == 2
            assert opportunities[0]["apy"] == 0.5

    async def test_enter_farm(self, yield_farming_manager, test_private_key, test_address_from_private_key):
        """Test entering a yield farm."""
        with patch.object(yield_farming_manager, "_deposit_to_pool") as mock_deposit:
            mock_deposit.return_value = {"tx_hash": "0x" + "q" * 64, "status": "pending"}
            result = await yield_farming_manager.enter_farm(
                pool="ETH-USDC",
                amount=1000,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "q" * 64

    async def test_exit_farm(self, yield_farming_manager, test_private_key, test_address_from_private_key):
        """Test exiting a yield farm."""
        with patch.object(yield_farming_manager, "_withdraw_from_pool") as mock_withdraw:
            mock_withdraw.return_value = {"tx_hash": "0x" + "r" * 64, "status": "completed"}
            result = await yield_farming_manager.exit_farm(
                pool="ETH-USDC",
                amount=500,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "r" * 64


# ============================== INTEGRATION TESTS ==============================

class TestDeFiIntegration:
    """Integration tests for DeFi components working together."""

    async def test_full_flow_supply_borrow_repay(self, aave_protocol, test_private_key, test_address_from_private_key):
        """Test a complete cycle: supply -> borrow -> repay -> withdraw."""
        # 1. Supply USDC
        with patch.object(aave_protocol.lending_pool.functions, "deposit") as mock_deposit:
            mock_deposit.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(aave_protocol.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "s" * 64
                with patch.object(aave_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "s" * 64}
                    await aave_protocol.deposit(
                        asset="USDC", amount=1000,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
        # 2. Borrow WETH
        with patch.object(aave_protocol.lending_pool.functions, "borrow") as mock_borrow:
            mock_borrow.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(aave_protocol.web3_client.eth, "send_transaction") as mock_send2:
                mock_send2.return_value = "0x" + "t" * 64
                with patch.object(aave_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait2:
                    mock_wait2.return_value = {"status": 1, "transactionHash": "0x" + "t" * 64}
                    await aave_protocol.borrow(
                        asset="WETH", amount=0.5,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
        # 3. Repay WETH
        with patch.object(aave_protocol.lending_pool.functions, "repay") as mock_repay:
            mock_repay.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(aave_protocol.web3_client.eth, "send_transaction") as mock_send3:
                mock_send3.return_value = "0x" + "u" * 64
                with patch.object(aave_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait3:
                    mock_wait3.return_value = {"status": 1, "transactionHash": "0x" + "u" * 64}
                    await aave_protocol.repay(
                        asset="WETH", amount=0.5,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
        # 4. Withdraw USDC
        with patch.object(aave_protocol.lending_pool.functions, "withdraw") as mock_withdraw:
            mock_withdraw.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(aave_protocol.web3_client.eth, "send_transaction") as mock_send4:
                mock_send4.return_value = "0x" + "v" * 64
                with patch.object(aave_protocol.web3_client.eth, "wait_for_transaction_receipt") as mock_wait4:
                    mock_wait4.return_value = {"status": 1, "transactionHash": "0x" + "v" * 64}
                    await aave_protocol.withdraw(
                        asset="USDC", amount=1000,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
        # All operations should have succeeded; we just check that mocks were called.
        # We could assert call counts.

    async def test_deep_swap_with_aggregator(self, defi_aggregator):
        """Test a complex swap using the aggregator with multiple protocols."""
        # Mock routes from protocols
        routes = [
            {"protocol": "Uniswap", "amount": 600, "output": 1200},
            {"protocol": "Sushiswap", "amount": 400, "output": 780},
        ]
        with patch.object(defi_aggregator, "_get_optimal_routes", return_value=routes):
            result = await defi_aggregator.aggregate_swap(
                token_in="USDC",
                token_out="WETH",
                amount_in=1000,
            )
            assert result["total_output"] == 1980
            # Verify routes were used
            assert len(result["routes"]) == 2

    async def test_risk_management_with_asset_allocation(self, defi_risk_manager):
        """Test risk-based asset allocation across protocols."""
        # Simulate recommendations
        with patch.object(defi_risk_manager, "_analyze_protocols") as mock_analyze:
            mock_analyze.return_value = [
                {"protocol": "Aave", "risk_score": 0.8, "apy": 0.05, "allocation": 0.5},
                {"protocol": "Compound", "risk_score": 0.9, "apy": 0.04, "allocation": 0.3},
                {"protocol": "Curve", "risk_score": 0.7, "apy": 0.06, "allocation": 0.2},
            ]
            allocation = await defi_risk_manager.suggest_allocation(assets=["USDC", "DAI"], total_amount=10000)
            assert sum(allocation.values()) == 10000
            assert "Aave" in allocation
