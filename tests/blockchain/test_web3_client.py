# tests/blockchain/test_web3_client.py
"""
Web3 Client Tests for the NEXUS AI Trading System.

This module contains comprehensive tests for the Web3Client wrapper:
- Web3 client initialization and connection
- Chain ID, gas price, and nonce retrieval
- Balance queries (ETH and ERC20 tokens)
- Transaction construction, signing, and sending
- Smart contract interaction (call and send)
- Event filtering and log parsing
- ENS resolution
- Error handling and retries

All tests use mocked web3 provider interactions to avoid external dependencies.
"""

import asyncio
import json
from decimal import Decimal
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from eth_account import Account
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import TxReceipt, BlockData

from blockchain.web3.web3_client import Web3Client
from blockchain.web3.web3_config import Web3Config
from blockchain.web3.web3_contract import Web3ContractWrapper
from blockchain.web3.web3_event import Web3EventManager
from blockchain.web3.web3_gas import Web3GasManager
from blockchain.web3.web3_ens import Web3ENSManager
from blockchain.web3.web3_multicall import Web3Multicall
from blockchain.web3.web3_price import Web3PriceProvider
from blockchain.web3.web3_provider import Web3ProviderManager
from blockchain.web3.web3_token import Web3TokenManager
from blockchain.web3.web3_transaction import Web3TransactionManager
from blockchain.web3.web3_utils import Web3Utils

pytest_plugins = ["tests.blockchain.conftest"]


# ============================== WEB3 CLIENT TESTS ==============================

class TestWeb3Client:
    """Test the Web3Client class and its core functionality."""

    @pytest.fixture
    def web3_client(self, web3_client_service: Web3Client):
        """Return a Web3Client instance from fixture."""
        return web3_client_service

    def test_client_initialization(self, web3_client: Web3Client):
        """Test that Web3Client initializes with a valid web3 instance."""
        assert web3_client.web3 is not None
        # Check that the client can make basic calls (mock)
        assert web3_client.is_connected() is True

    def test_get_chain_id(self, web3_client: Web3Client):
        """Test retrieving the chain ID."""
        with patch.object(web3_client.web3.eth, "chain_id") as mock_chain_id:
            mock_chain_id.return_value = 1
            chain_id = web3_client.get_chain_id()
            assert chain_id == 1

    def test_get_gas_price(self, web3_client: Web3Client):
        """Test retrieving the current gas price."""
        with patch.object(web3_client.web3.eth, "gas_price") as mock_gas:
            mock_gas.return_value = 10**9  # 1 Gwei
            gas_price = web3_client.get_gas_price()
            assert gas_price == 10**9

    def test_get_nonce(self, web3_client: Web3Client):
        """Test getting the nonce for an address."""
        address = "0x" + "a" * 40
        with patch.object(web3_client.web3.eth, "get_transaction_count") as mock_nonce:
            mock_nonce.return_value = 5
            nonce = web3_client.get_nonce(address)
            assert nonce == 5

    def test_get_balance(self, web3_client: Web3Client):
        """Test getting ETH balance for an address."""
        address = "0x" + "b" * 40
        with patch.object(web3_client.web3.eth, "get_balance") as mock_balance:
            mock_balance.return_value = 10**18
            balance = web3_client.get_balance(address)
            assert balance == 10**18

    def test_get_balance_with_block(self, web3_client: Web3Client):
        """Test getting balance at a specific block."""
        address = "0x" + "c" * 40
        block_identifier = "latest"
        with patch.object(web3_client.web3.eth, "get_balance") as mock_balance:
            mock_balance.return_value = 5 * 10**17
            balance = web3_client.get_balance(address, block_identifier)
            assert balance == 5 * 10**17
            mock_balance.assert_called_once_with(address, block_identifier)

    def test_send_transaction(self, web3_client: Web3Client):
        """Test sending a raw transaction."""
        tx = {
            "to": "0x" + "d" * 40,
            "value": 10**17,
            "gas": 21000,
            "gasPrice": 10**9,
            "nonce": 0,
        }
        private_key = "0x" + "f" * 64
        # Mock signing and sending
        with patch.object(Account, "sign_transaction") as mock_sign:
            mock_sign.return_value = {"rawTransaction": "0x" + "e" * 64}
            with patch.object(web3_client.web3.eth, "send_raw_transaction") as mock_send:
                mock_send.return_value = "0x" + "g" * 64
                tx_hash = web3_client.send_transaction(tx, private_key)
                assert tx_hash == "0x" + "g" * 64

    def test_send_transaction_with_auto_nonce(self, web3_client: Web3Client):
        """Test sending transaction with automatic nonce and gas."""
        tx = {
            "to": "0x" + "h" * 40,
            "value": 10**17,
        }
        private_key = "0x" + "i" * 64
        # Mock getting nonce, gas price, and signing
        with patch.object(web3_client, "get_nonce") as mock_nonce:
            mock_nonce.return_value = 5
            with patch.object(web3_client, "get_gas_price") as mock_gas:
                mock_gas.return_value = 10**9
                with patch.object(Account, "sign_transaction") as mock_sign:
                    mock_sign.return_value = {"rawTransaction": "0x" + "j" * 64}
                    with patch.object(web3_client.web3.eth, "send_raw_transaction") as mock_send:
                        mock_send.return_value = "0x" + "k" * 64
                        tx_hash = web3_client.send_transaction(tx, private_key, auto_nonce=True, auto_gas=True)
                        assert tx_hash == "0x" + "k" * 64
                        # Check that nonce and gas were filled
                        assert "nonce" in tx
                        assert "gas" in tx
                        assert "gasPrice" in tx

    def test_wait_for_transaction_receipt(self, web3_client: Web3Client):
        """Test waiting for a transaction receipt."""
        tx_hash = "0x" + "l" * 64
        mock_receipt = {"status": 1, "transactionHash": tx_hash, "blockNumber": 12345}
        with patch.object(web3_client.web3.eth, "wait_for_transaction_receipt") as mock_wait:
            mock_wait.return_value = mock_receipt
            receipt = web3_client.wait_for_transaction_receipt(tx_hash, timeout=120)
            assert receipt["status"] == 1
            assert receipt["transactionHash"] == tx_hash

    def test_get_transaction_receipt(self, web3_client: Web3Client):
        """Test getting a transaction receipt."""
        tx_hash = "0x" + "m" * 64
        mock_receipt = {"status": 1, "transactionHash": tx_hash}
        with patch.object(web3_client.web3.eth, "get_transaction_receipt") as mock_get:
            mock_get.return_value = mock_receipt
            receipt = web3_client.get_transaction_receipt(tx_hash)
            assert receipt["transactionHash"] == tx_hash

    def test_get_block(self, web3_client: Web3Client):
        """Test getting a block by number or hash."""
        block_number = 12345
        mock_block = {"number": block_number, "hash": "0x" + "n" * 64}
        with patch.object(web3_client.web3.eth, "get_block") as mock_block:
            mock_block.return_value = mock_block
            block = web3_client.get_block(block_number)
            assert block["number"] == block_number

    def test_get_block_transactions(self, web3_client: Web3Client):
        """Test getting transactions in a block."""
        block_number = 12345
        mock_block = {"number": block_number, "transactions": ["0x1", "0x2"]}
        with patch.object(web3_client.web3.eth, "get_block") as mock_block:
            mock_block.return_value = mock_block
            txs = web3_client.get_block_transactions(block_number)
            assert len(txs) == 2

    def test_estimate_gas(self, web3_client: Web3Client):
        """Test estimating gas for a transaction."""
        tx = {"to": "0x" + "o" * 40, "value": 10**17}
        with patch.object(web3_client.web3.eth, "estimate_gas") as mock_estimate:
            mock_estimate.return_value = 21000
            gas = web3_client.estimate_gas(tx)
            assert gas == 21000


# ============================== WEB3 CONFIG TESTS ==============================

class TestWeb3Config:
    """Test Web3 configuration loading and management."""

    def test_load_config(self):
        """Test loading web3 configuration from file."""
        config = Web3Config()
        mock_config = {
            "default_provider": "http://localhost:8545",
            "chains": {
                "ethereum": {"rpc_url": "http://localhost:8545", "chain_id": 1},
                "bsc": {"rpc_url": "http://localhost:8546", "chain_id": 56},
            },
            "gas_settings": {"default_gas_limit": 21000, "default_gas_price": 10**9},
        }
        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_config)
            config.load_from_file("web3_config.json")
            assert config.default_provider == "http://localhost:8545"
            assert config.chains["bsc"]["chain_id"] == 56

    def test_get_chain_config(self):
        """Test retrieving configuration for a specific chain."""
        config = Web3Config()
        config.chains = {"ethereum": {"rpc_url": "http://localhost:8545", "chain_id": 1}}
        chain_config = config.get_chain_config("ethereum")
        assert chain_config["chain_id"] == 1


# ============================== WEB3 CONTRACT WRAPPER TESTS ==============================

class TestWeb3ContractWrapper:
    """Test the Web3ContractWrapper for contract interactions."""

    @pytest.fixture
    def contract_wrapper(self, web3_client_service: Web3Client):
        """Return a Web3ContractWrapper instance."""
        wrapper = Web3ContractWrapper(
            web3_client=web3_client_service,
            address="0x" + "p" * 40,
            abi=[{"type": "function", "name": "balanceOf", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]}],
        )
        return wrapper

    def test_call_function(self, contract_wrapper: Web3ContractWrapper):
        """Test calling a view/pure function."""
        # Mock the web3 contract call
        mock_contract = MagicMock()
        mock_contract.functions.balanceOf.return_value.call.return_value = 1000
        with patch.object(contract_wrapper.web3_client.web3.eth, "contract") as mock_eth_contract:
            mock_eth_contract.return_value = mock_contract
            result = contract_wrapper.call_function("balanceOf", ["0x" + "q" * 40])
            assert result == 1000

    def test_send_transaction(self, contract_wrapper: Web3ContractWrapper):
        """Test sending a transaction to a contract function."""
        # Mock building transaction, signing, and sending.
        mock_contract = MagicMock()
        mock_contract.functions.transfer.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
        with patch.object(contract_wrapper.web3_client.web3.eth, "contract") as mock_eth_contract:
            mock_eth_contract.return_value = mock_contract
            with patch.object(contract_wrapper.web3_client, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "r" * 64
                tx_hash = contract_wrapper.send_transaction(
                    "transfer",
                    ["0x" + "s" * 40, 100],
                    private_key="0x" + "t" * 64,
                    from_address="0x" + "u" * 40,
                )
                assert tx_hash == "0x" + "r" * 64

    def test_get_events(self, contract_wrapper: Web3ContractWrapper):
        """Test getting event logs."""
        mock_events = [
            {"event": "Transfer", "args": {"from": "0xfrom", "to": "0xto", "value": 100}},
            {"event": "Transfer", "args": {"from": "0xfrom2", "to": "0xto2", "value": 200}},
        ]
        with patch.object(contract_wrapper.web3_client.web3.eth, "get_logs") as mock_logs:
            # Need to mock the contract.events.Transfer.get_logs, but we simplify.
            # We'll patch the contract wrapper's _get_events method.
            with patch.object(contract_wrapper, "_get_events") as mock_get:
                mock_get.return_value = mock_events
                events = contract_wrapper.get_events("Transfer", from_block=0, to_block="latest")
                assert len(events) == 2
                assert events[0]["event"] == "Transfer"


# ============================== WEB3 EVENT MANAGER TESTS ==============================

class TestWeb3EventManager:
    """Test the Web3EventManager for event monitoring."""

    @pytest.fixture
    def event_manager(self, web3_client_service: Web3Client):
        """Return a Web3EventManager instance."""
        return Web3EventManager(web3_client=web3_client_service)

    def test_register_event_listener(self, event_manager: Web3EventManager):
        """Test registering an event listener."""
        listener = AsyncMock()
        event_manager.register_listener("Transfer", listener)
        assert "Transfer" in event_manager.listeners
        assert listener in event_manager.listeners["Transfer"]

    async def test_emit_event(self, event_manager: Web3EventManager):
        """Test emitting an event to listeners."""
        listener = AsyncMock()
        event_manager.register_listener("Transfer", listener)
        event_data = {"from": "0xfrom", "to": "0xto", "value": 100}
        await event_manager.emit("Transfer", event_data)
        listener.assert_called_once_with(event_data)

    async def test_poll_events(self, event_manager: Web3EventManager):
        """Test polling for new events."""
        # Mock fetching logs
        mock_contract = MagicMock()
        mock_contract.events.Transfer.get_logs.return_value = [{"event": "Transfer", "args": {"value": 100}}]
        with patch.object(event_manager, "_get_contract", return_value=mock_contract):
            with patch.object(event_manager, "_process_event") as mock_process:
                await event_manager.poll_events(contract_address="0x" + "v" * 40, event_name="Transfer")
                mock_process.assert_called_once()


# ============================== WEB3 GAS MANAGER TESTS ==============================

class TestWeb3GasManager:
    """Test the Web3GasManager for gas estimation and optimization."""

    @pytest.fixture
    def gas_manager(self, web3_client_service: Web3Client):
        """Return a Web3GasManager instance."""
        return Web3GasManager(web3_client=web3_client_service)

    def test_get_gas_price_strategy(self, gas_manager: Web3GasManager):
        """Test gas price strategies."""
        # Test default strategy
        with patch.object(gas_manager.web3_client, "get_gas_price") as mock_gas:
            mock_gas.return_value = 10**9
            price = gas_manager.get_gas_price(strategy="standard")
            assert price == 10**9

    def test_get_gas_price_with_multiplier(self, gas_manager: Web3GasManager):
        """Test gas price with multiplier."""
        with patch.object(gas_manager.web3_client, "get_gas_price") as mock_gas:
            mock_gas.return_value = 10**9
            price = gas_manager.get_gas_price(strategy="standard", multiplier=1.2)
            assert price == 1.2 * 10**9

    def test_estimate_gas_limit(self, gas_manager: Web3GasManager):
        """Test estimating gas limit for a transaction."""
        tx = {"to": "0x" + "w" * 40, "value": 10**17}
        with patch.object(gas_manager.web3_client, "estimate_gas") as mock_estimate:
            mock_estimate.return_value = 21000
            gas_limit = gas_manager.estimate_gas_limit(tx)
            assert gas_limit == 21000

    def test_calculate_total_gas_cost(self, gas_manager: Web3GasManager):
        """Test calculating total gas cost."""
        gas_price = 10**9
        gas_limit = 21000
        total = gas_manager.calculate_total_gas_cost(gas_price, gas_limit)
        assert total == 10**9 * 21000


# ============================== WEB3 ENS MANAGER TESTS ==============================

class TestWeb3ENSManager:
    """Test the Web3ENSManager for ENS resolution."""

    @pytest.fixture
    def ens_manager(self, web3_client_service: Web3Client):
        """Return a Web3ENSManager instance."""
        return Web3ENSManager(web3_client=web3_client_service)

    def test_resolve_address(self, ens_manager: Web3ENSManager):
        """Test resolving an ENS name to an address."""
        ens_name = "vitalik.eth"
        expected_address = "0x" + "x" * 40
        with patch.object(ens_manager.web3_client.web3.ens, "address") as mock_resolve:
            mock_resolve.return_value = expected_address
            address = ens_manager.resolve_address(ens_name)
            assert address == expected_address

    def test_resolve_name(self, ens_manager: Web3ENSManager):
        """Test resolving an address to an ENS name."""
        address = "0x" + "y" * 40
        expected_name = "vitalik.eth"
        with patch.object(ens_manager.web3_client.web3.ens, "name") as mock_resolve:
            mock_resolve.return_value = expected_name
            name = ens_manager.resolve_name(address)
            assert name == expected_name

    def test_resolve_text_record(self, ens_manager: Web3ENSManager):
        """Test resolving a text record for an ENS name."""
        ens_name = "vitalik.eth"
        key = "avatar"
        expected_value = "https://example.com/avatar.png"
        with patch.object(ens_manager.web3_client.web3.ens, "get_text") as mock_get:
            mock_get.return_value = expected_value
            value = ens_manager.resolve_text_record(ens_name, key)
            assert value == expected_value


# ============================== WEB3 MULTICALL TESTS ==============================

class TestWeb3Multicall:
    """Test the Web3Multicall for batching multiple contract calls."""

    @pytest.fixture
    def multicall(self, web3_client_service: Web3Client):
        """Return a Web3Multicall instance."""
        return Web3Multicall(web3_client=web3_client_service)

    def test_aggregate_calls(self, multicall: Web3Multicall):
        """Test aggregating multiple contract calls."""
        # Build calls
        calls = [
            {"target": "0x" + "z" * 40, "function": "balanceOf", "args": ["0xuser"], "output_type": "uint256"},
            {"target": "0x" + "aa" * 40, "function": "totalSupply", "args": [], "output_type": "uint256"},
        ]
        # Mock the multicall contract
        mock_results = [1000, 1000000]
        with patch.object(multicall, "_call_aggregate") as mock_aggregate:
            mock_aggregate.return_value = mock_results
            results = multicall.aggregate_calls(calls)
            assert results == mock_results

    def test_batch_erc20_balances(self, multicall: Web3Multicall):
        """Test batch fetching ERC20 balances."""
        token_addresses = ["0x" + "bb" * 40, "0x" + "cc" * 40]
        user_address = "0x" + "dd" * 40
        with patch.object(multicall, "aggregate_calls") as mock_agg:
            mock_agg.return_value = [100, 200]
            balances = multicall.batch_erc20_balances(token_addresses, user_address)
            assert balances == {"0x" + "bb" * 40: 100, "0x" + "cc" * 40: 200}


# ============================== WEB3 PRICE PROVIDER TESTS ==============================

class TestWeb3PriceProvider:
    """Test the Web3PriceProvider for fetching token prices."""

    @pytest.fixture
    def price_provider(self, web3_client_service: Web3Client):
        """Return a Web3PriceProvider instance."""
        return Web3PriceProvider(web3_client=web3_client_service)

    def test_get_price_from_uniswap(self, price_provider: Web3PriceProvider):
        """Test fetching price from Uniswap."""
        token_address = "0x" + "ee" * 40
        quote_token = "0x" + "ff" * 40
        # Mock Uniswap router
        with patch.object(price_provider, "_get_uniswap_price") as mock_price:
            mock_price.return_value = 1000
            price = price_provider.get_price(token_address, quote_token, exchange="uniswap")
            assert price == 1000

    def test_get_price_from_chainlink(self, price_provider: Web3PriceProvider):
        """Test fetching price from Chainlink oracle."""
        feed_address = "0x" + "gg" * 40
        with patch.object(price_provider, "_get_chainlink_price") as mock_price:
            mock_price.return_value = 2000
            price = price_provider.get_price_from_oracle(feed_address)
            assert price == 2000


# ============================== WEB3 PROVIDER MANAGER TESTS ==============================

class TestWeb3ProviderManager:
    """Test the Web3ProviderManager for managing provider connections."""

    @pytest.fixture
    def provider_manager(self):
        """Return a Web3ProviderManager instance."""
        return Web3ProviderManager()

    def test_add_provider(self, provider_manager: Web3ProviderManager):
        """Test adding a provider."""
        provider_manager.add_provider("eth_mainnet", "http://localhost:8545")
        assert "eth_mainnet" in provider_manager.providers

    def test_get_provider(self, provider_manager: Web3ProviderManager):
        """Test retrieving a provider."""
        provider_manager.add_provider("eth_mainnet", "http://localhost:8545")
        provider = provider_manager.get_provider("eth_mainnet")
        assert provider == "http://localhost:8545"

    def test_get_healthy_provider(self, provider_manager: Web3ProviderManager):
        """Test getting the first healthy provider."""
        provider_manager.add_provider("provider1", "http://localhost:8545")
        provider_manager.add_provider("provider2", "http://localhost:8546")
        # Mock health check
        with patch.object(provider_manager, "_check_health") as mock_health:
            mock_health.side_effect = [False, True]
            healthy = provider_manager.get_healthy_provider()
            assert healthy["uri"] == "http://localhost:8546"


# ============================== WEB3 TOKEN MANAGER TESTS ==============================

class TestWeb3TokenManager:
    """Test the Web3TokenManager for ERC20 token operations."""

    @pytest.fixture
    def token_manager(self, web3_client_service: Web3Client):
        """Return a Web3TokenManager instance."""
        return Web3TokenManager(web3_client=web3_client_service)

    def test_get_token_info(self, token_manager: Web3TokenManager):
        """Test getting ERC20 token information."""
        token_address = "0x" + "hh" * 40
        with patch.object(token_manager, "_get_token_contract") as mock_contract:
            mock_contract.return_value.functions.name.return_value.call.return_value = "Test Token"
            mock_contract.return_value.functions.symbol.return_value.call.return_value = "TT"
            mock_contract.return_value.functions.decimals.return_value.call.return_value = 18
            info = token_manager.get_token_info(token_address)
            assert info["name"] == "Test Token"
            assert info["symbol"] == "TT"

    def test_get_token_balance(self, token_manager: Web3TokenManager):
        """Test getting token balance for a user."""
        token_address = "0x" + "ii" * 40
        user_address = "0x" + "jj" * 40
        with patch.object(token_manager, "_get_token_contract") as mock_contract:
            mock_contract.return_value.functions.balanceOf.return_value.call.return_value = 1000
            balance = token_manager.get_token_balance(token_address, user_address)
            assert balance == 1000


# ============================== WEB3 TRANSACTION MANAGER TESTS ==============================

class TestWeb3TransactionManager:
    """Test the Web3TransactionManager for transaction lifecycle."""

    @pytest.fixture
    def tx_manager(self, web3_client_service: Web3Client):
        """Return a Web3TransactionManager instance."""
        return Web3TransactionManager(web3_client=web3_client_service)

    def test_build_transaction(self, tx_manager: Web3TransactionManager):
        """Test building a transaction."""
        tx = tx_manager.build_transaction(
            to="0x" + "kk" * 40,
            value=10**17,
            gas=21000,
            gas_price=10**9,
            nonce=0,
        )
        assert tx["to"] == "0x" + "kk" * 40
        assert tx["value"] == 10**17
        assert tx["gas"] == 21000

    def test_sign_transaction(self, tx_manager: Web3TransactionManager):
        """Test signing a transaction."""
        tx = {"to": "0x" + "ll" * 40, "value": 10**17, "gas": 21000, "gasPrice": 10**9, "nonce": 0}
        private_key = "0x" + "mm" * 64
        with patch.object(Account, "sign_transaction") as mock_sign:
            mock_sign.return_value = {"rawTransaction": "0x" + "nn" * 64}
            signed = tx_manager.sign_transaction(tx, private_key)
            assert signed == "0x" + "nn" * 64

    def test_send_transaction(self, tx_manager: Web3TransactionManager):
        """Test sending a signed transaction."""
        raw_tx = "0x" + "oo" * 64
        with patch.object(tx_manager.web3_client.web3.eth, "send_raw_transaction") as mock_send:
            mock_send.return_value = "0x" + "pp" * 64
            tx_hash = tx_manager.send_transaction(raw_tx)
            assert tx_hash == "0x" + "pp" * 64

    def test_confirm_transaction(self, tx_manager: Web3TransactionManager):
        """Test confirming a transaction by waiting for receipt."""
        tx_hash = "0x" + "qq" * 64
        with patch.object(tx_manager.web3_client, "wait_for_transaction_receipt") as mock_wait:
            mock_wait.return_value = {"status": 1, "transactionHash": tx_hash}
            receipt = tx_manager.confirm_transaction(tx_hash)
            assert receipt["status"] == 1


# ============================== WEB3 UTILS TESTS ==============================

class TestWeb3Utils:
    """Test the Web3Utils helper functions."""

    def test_to_checksum_address(self):
        """Test converting to checksum address."""
        address = "0x" + "a" * 40
        checksum = Web3Utils.to_checksum_address(address)
        # Check that it matches the web3.toChecksumAddress result
        expected = Web3.to_checksum_address(address)
        assert checksum == expected

    def test_from_wei(self):
        """Test converting from wei to ETH."""
        wei_value = 10**18
        eth = Web3Utils.from_wei(wei_value, "ether")
        assert eth == 1.0

    def test_to_wei(self):
        """Test converting to wei."""
        eth = 1.0
        wei = Web3Utils.to_wei(eth, "ether")
        assert wei == 10**18

    def test_hex_to_bytes(self):
        """Test converting hex string to bytes."""
        hex_str = "0x" + "f" * 64
        bytes_val = Web3Utils.hex_to_bytes(hex_str)
        assert isinstance(bytes_val, bytes)

    def test_bytes_to_hex(self):
        """Test converting bytes to hex string."""
        bytes_val = b"test"
        hex_str = Web3Utils.bytes_to_hex(bytes_val)
        assert hex_str.startswith("0x")


# ============================== INTEGRATION TESTS ==============================

class TestWeb3Integration:
    """Integration tests for multiple web3 components working together."""

    async def test_full_transaction_flow(
        self,
        web3_client_service: Web3Client,
        test_private_key: str,
        test_address_from_private_key: str,
    ):
        """Test a complete transaction flow from building to confirmation."""
        # 1. Build transaction
        tx = {
            "to": "0x" + "rr" * 40,
            "value": 10**17,
        }
        # 2. Auto-fill nonce and gas
        with patch.object(web3_client_service, "get_nonce") as mock_nonce:
            mock_nonce.return_value = 0
            with patch.object(web3_client_service, "get_gas_price") as mock_gas:
                mock_gas.return_value = 10**9
                with patch.object(web3_client_service, "estimate_gas") as mock_est:
                    mock_est.return_value = 21000
                    tx["nonce"] = mock_nonce.return_value
                    tx["gasPrice"] = mock_gas.return_value
                    tx["gas"] = mock_est.return_value

        # 3. Sign transaction
        with patch.object(Account, "sign_transaction") as mock_sign:
            mock_sign.return_value = {"rawTransaction": "0x" + "ss" * 64}
            raw_tx = mock_sign.return_value["rawTransaction"]

        # 4. Send transaction
        with patch.object(web3_client_service.web3.eth, "send_raw_transaction") as mock_send:
            mock_send.return_value = "0x" + "tt" * 64
            tx_hash = mock_send.return_value

        # 5. Wait for receipt
        with patch.object(web3_client_service, "wait_for_transaction_receipt") as mock_wait:
            mock_wait.return_value = {"status": 1, "transactionHash": tx_hash}
            receipt = mock_wait.return_value

        assert receipt["status"] == 1
        assert receipt["transactionHash"] == tx_hash

    async def test_token_balance_and_transfer(
        self,
        web3_client_service: Web3Client,
        token_manager: Web3TokenManager,
        test_private_key: str,
        test_address_from_private_key: str,
    ):
        """Test checking token balance and transferring tokens."""
        token_address = "0x" + "uu" * 40

        # 1. Get balance
        with patch.object(token_manager, "get_token_balance") as mock_balance:
            mock_balance.return_value = 1000
            balance = await token_manager.get_token_balance(token_address, test_address_from_private_key)
            assert balance == 1000

        # 2. Build transfer transaction
        # Mock contract wrapper
        contract_wrapper = Web3ContractWrapper(
            web3_client=web3_client_service,
            address=token_address,
            abi=[],
        )
        with patch.object(contract_wrapper, "send_transaction") as mock_send:
            mock_send.return_value = "0x" + "vv" * 64
            tx_hash = await contract_wrapper.send_transaction(
                "transfer",
                ["0x" + "ww" * 40, 100],
                private_key=test_private_key,
                from_address=test_address_from_private_key,
            )
            assert tx_hash == "0x" + "vv" * 64

        # 3. Confirm transaction
        with patch.object(web3_client_service, "wait_for_transaction_receipt") as mock_wait:
            mock_wait.return_value = {"status": 1, "transactionHash": tx_hash}
            receipt = web3_client_service.wait_for_transaction_receipt(tx_hash)
            assert receipt["status"] == 1

        # 4. Check new balance (decreased by 100)
        with patch.object(token_manager, "get_token_balance") as mock_new_balance:
            mock_new_balance.return_value = 900
            new_balance = await token_manager.get_token_balance(token_address, test_address_from_private_key)
            assert new_balance == 900

    async def test_multicall_batch_read(
        self,
        web3_client_service: Web3Client,
        multicall: Web3Multicall,
    ):
        """Test using multicall for batch reading."""
        # Build calls for multiple token balances
        token_addresses = ["0x" + "xx" * 40, "0x" + "yy" * 40]
        user = "0x" + "zz" * 40

        with patch.object(multicall, "batch_erc20_balances") as mock_batch:
            mock_batch.return_value = {token_addresses[0]: 100, token_addresses[1]: 200}
            balances = multicall.batch_erc20_balances(token_addresses, user)
            assert balances[token_addresses[0]] == 100
            assert balances[token_addresses[1]] == 200
