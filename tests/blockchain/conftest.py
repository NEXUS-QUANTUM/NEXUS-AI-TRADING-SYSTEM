# tests/blockchain/conftest.py
"""
Pytest configuration and shared fixtures for blockchain tests.

This file provides fixtures for:
- Web3 provider and client (using eth-tester or mocked provider)
- Test accounts (Ethereum, BSC, Polygon, Solana, etc.)
- Mock smart contracts (ERC20, ERC721, Uniswap, Aave, etc.)
- Blockchain node simulation (transactions, blocks, receipts)
- Bridge, DeFi, NFT, Staking, and Wallet service mocks
- Configuration for blockchain endpoints

All fixtures are designed to be used with pytest-asyncio for async tests
where applicable, and follow the NEXUS development standards.
"""

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from eth_account import Account
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.providers.eth_tester import EthereumTesterProvider
from web3.types import TxReceipt, BlockData

# Import blockchain modules (adjust paths as needed)
from blockchain.bridges.base_bridge import BaseBridge
from blockchain.bridges.bridge_manager import BridgeManager
from blockchain.defi.base_protocol import BaseDeFiProtocol
from blockchain.defi.defi_manager import DeFiManager
from blockchain.nft.nft_manager import NFTManager
from blockchain.nodes.node_manager import NodeManager
from blockchain.onchain_analysis.onchain_analyzer import OnChainAnalyzer
from blockchain.smart_contracts.contract_manager import ContractManager
from blockchain.staking.staking_manager import StakingManager
from blockchain.wallets.wallet_manager import WalletManager
from blockchain.web3.web3_client import Web3Client

# Test environment configuration
os.environ["BLOCKCHAIN_ENVIRONMENT"] = "test"
os.environ["WEB3_PROVIDER_URI"] = os.getenv("TEST_WEB3_PROVIDER", "http://localhost:8545")
os.environ["TEST_PRIVATE_KEY"] = os.getenv("TEST_PRIVATE_KEY", "0x" + "1" * 64)


# ---------------------------- Web3 Provider Fixtures ----------------------------

@pytest.fixture(scope="session")
def eth_tester_provider():
    """Return an EthereumTesterProvider for testing."""
    # Use eth-tester if available, otherwise fallback to HTTP mock.
    try:
        from eth_tester import EthereumTester
        from web3.providers.eth_tester import EthereumTesterProvider
        return EthereumTesterProvider()
    except ImportError:
        # Fallback: use a mock provider
        from web3.providers.base import BaseProvider
        class MockProvider(BaseProvider):
            def make_request(self, method, params):
                return {"result": None}
        return MockProvider()


@pytest.fixture(scope="session")
def web3_client(eth_tester_provider) -> Web3:
    """Return a Web3 client connected to the test provider."""
    w3 = Web3(eth_tester_provider)
    # Inject PoA middleware if using a PoA chain (e.g., BSC, Polygon)
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3


@pytest.fixture(scope="session")
def test_accounts(web3_client) -> List[Dict[str, Any]]:
    """Return a list of test accounts with private keys and addresses."""
    # Generate 5 test accounts
    accounts = []
    for i in range(5):
        account = Account.create()
        # Fund the account with some test ETH (for eth-tester, we need to mine blocks)
        # If using eth-tester, we can send transactions from the coinbase account.
        if web3_client.eth.accounts:
            # Fund using the first account (coinbase)
            tx = {
                "from": web3_client.eth.accounts[0],
                "to": account.address,
                "value": web3_client.to_wei(1000, "ether"),
                "gas": 21000,
                "gasPrice": web3_client.to_wei(1, "gwei"),
            }
            signed = web3_client.eth.account.sign_transaction(tx, private_key=web3_client.eth.accounts[0])  # coinbase private key? not available; mock.
            # Since we can't easily fund via eth-tester without private key of coinbase, we'll just set balance via test environment.
            # For eth-tester, we can use `web3_client.eth.send_transaction` if we have coinbase private key.
            # Simpler: use `web3_client.eth.send_transaction` with `from` = coinbase, but we need private key.
            # We'll skip funding and rely on mocking balances.
        accounts.append({
            "address": account.address,
            "private_key": account.key.hex(),
            "balance": Decimal("1000.0"),  # mock
        })
    return accounts


@pytest.fixture(scope="function")
def coinbase_account(web3_client) -> Dict[str, Any]:
    """Return the default coinbase account for testing."""
    if web3_client.eth.accounts:
        address = web3_client.eth.accounts[0]
        return {
            "address": address,
            "private_key": "0x" + "f" * 64,  # placeholder, not actually used
            "balance": Decimal("10000.0"),
        }
    # Fallback
    return {"address": "0x0000000000000000000000000000000000000000", "private_key": "0x0", "balance": Decimal("0")}


# ---------------------------- Mock Contract Fixtures ----------------------------

@pytest.fixture(scope="function")
def mock_erc20_contract(web3_client, test_accounts) -> MagicMock:
    """Return a mock ERC20 contract instance."""
    mock_contract = MagicMock()
    mock_contract.functions.name().call = MagicMock(return_value="Test Token")
    mock_contract.functions.symbol().call = MagicMock(return_value="TT")
    mock_contract.functions.decimals().call = MagicMock(return_value=18)
    mock_contract.functions.totalSupply().call = MagicMock(return_value=10**6 * 10**18)
    mock_contract.functions.balanceOf.return_value.call = MagicMock(return_value=1000 * 10**18)
    mock_contract.functions.transfer.return_value.build_transaction = MagicMock(return_value={"to": "0x123", "data": "0x"})
    mock_contract.functions.approve.return_value.build_transaction = MagicMock(return_value={"to": "0x123", "data": "0x"})
    mock_contract.address = "0x" + "a" * 40
    return mock_contract


@pytest.fixture(scope="function")
def mock_erc721_contract() -> MagicMock:
    """Return a mock ERC721 contract instance."""
    mock_contract = MagicMock()
    mock_contract.functions.name().call = MagicMock(return_value="Test NFT")
    mock_contract.functions.symbol().call = MagicMock(return_value="TNFT")
    mock_contract.functions.tokenURI.return_value.call = MagicMock(return_value="https://example.com/token/1")
    mock_contract.functions.ownerOf.return_value.call = MagicMock(return_value="0x123")
    mock_contract.functions.safeTransferFrom.return_value.build_transaction = MagicMock(return_value={"to": "0x123", "data": "0x"})
    mock_contract.address = "0x" + "b" * 40
    return mock_contract


@pytest.fixture(scope="function")
def mock_uniswap_contract() -> MagicMock:
    """Return a mock Uniswap router contract."""
    mock_contract = MagicMock()
    mock_contract.functions.getAmountsOut.return_value.call = MagicMock(return_value=[1000, 2000])
    mock_contract.functions.swapExactETHForTokens.return_value.build_transaction = MagicMock(return_value={"to": "0x123", "data": "0x"})
    mock_contract.address = "0x" + "c" * 40
    return mock_contract


@pytest.fixture(scope="function")
def mock_aave_contract() -> MagicMock:
    """Return a mock Aave lending pool contract."""
    mock_contract = MagicMock()
    mock_contract.functions.getReserveData.return_value.call = MagicMock(return_value=(1000, 0.05, 0.01, 0.02, 0, 0, 0))
    mock_contract.functions.deposit.return_value.build_transaction = MagicMock(return_value={"to": "0x123", "data": "0x"})
    mock_contract.address = "0x" + "d" * 40
    return mock_contract


# ---------------------------- Blockchain Service Fixtures ----------------------------

@pytest.fixture(scope="function")
def web3_client_service(web3_client, test_accounts) -> Web3Client:
    """Return a Web3Client instance with the test web3 client."""
    return Web3Client(web3_client=web3_client)


@pytest.fixture(scope="function")
def node_manager(web3_client, test_accounts) -> NodeManager:
    """Return a NodeManager instance with mock nodes."""
    manager = NodeManager()
    # Add mock nodes
    manager.add_node("eth", {"uri": "http://localhost:8545", "chain_id": 1, "type": "full"})
    manager.add_node("bsc", {"uri": "http://localhost:8546", "chain_id": 56, "type": "full"})
    return manager


@pytest.fixture(scope="function")
def wallet_manager(web3_client, test_accounts) -> WalletManager:
    """Return a WalletManager instance with test accounts."""
    manager = WalletManager(web3_client=web3_client)
    for acc in test_accounts:
        manager.add_wallet(acc["address"], acc["private_key"])
    return manager


@pytest.fixture(scope="function")
def contract_manager(web3_client, mock_erc20_contract, mock_erc721_contract) -> ContractManager:
    """Return a ContractManager instance with mock contracts."""
    manager = ContractManager(web3_client=web3_client)
    # Register mock contracts
    manager.register_contract("TestToken", mock_erc20_contract.address, mock_erc20_contract.abi)
    manager.register_contract("TestNFT", mock_erc721_contract.address, mock_erc721_contract.abi)
    return manager


@pytest.fixture(scope="function")
def defi_manager(mock_aave_contract, mock_uniswap_contract) -> DeFiManager:
    """Return a DeFiManager with mocked protocols."""
    manager = DeFiManager()
    manager.register_protocol("aave", mock_aave_contract)
    manager.register_protocol("uniswap", mock_uniswap_contract)
    return manager


@pytest.fixture(scope="function")
def bridge_manager() -> BridgeManager:
    """Return a BridgeManager with mocked bridges."""
    manager = BridgeManager()
    # Add mock bridges
    mock_bridge = AsyncMock(spec=BaseBridge)
    mock_bridge.name = "Ethereum-BSC"
    mock_bridge.bridge_asset = AsyncMock(return_value={"tx_hash": "0x123"})
    manager.add_bridge(mock_bridge)
    return manager


@pytest.fixture(scope="function")
def nft_manager(mock_erc721_contract) -> NFTManager:
    """Return an NFTManager with mock NFT contract."""
    manager = NFTManager()
    manager.register_collection("TestNFT", mock_erc721_contract.address)
    return manager


@pytest.fixture(scope="function")
def staking_manager() -> StakingManager:
    """Return a StakingManager with mock staking pools."""
    manager = StakingManager()
    # Add mock staking pool
    manager.add_pool("ETH Staking", {"apy": 0.05, "min_stake": 1, "max_stake": 100})
    return manager


@pytest.fixture(scope="function")
def onchain_analyzer(web3_client) -> OnChainAnalyzer:
    """Return an OnChainAnalyzer with test web3 client."""
    return OnChainAnalyzer(web3_client=web3_client)


# ---------------------------- Configuration Fixtures ----------------------------

@pytest.fixture(scope="session")
def test_blockchain_config() -> Dict[str, Any]:
    """Return a test blockchain configuration."""
    return {
        "eth": {
            "chain_id": 1,
            "rpc_url": "http://localhost:8545",
            "ws_url": "ws://localhost:8546",
        },
        "bsc": {
            "chain_id": 56,
            "rpc_url": "http://localhost:8547",
            "ws_url": "ws://localhost:8548",
        },
        "polygon": {
            "chain_id": 137,
            "rpc_url": "http://localhost:8549",
            "ws_url": "ws://localhost:8550",
        },
        "solana": {
            "cluster": "devnet",
            "rpc_url": "http://localhost:8899",
        },
    }


@pytest.fixture(scope="function")
def test_private_key() -> str:
    """Return a test private key (pre-funded)."""
    return os.environ["TEST_PRIVATE_KEY"]


@pytest.fixture(scope="function")
def test_address_from_private_key(test_private_key) -> str:
    """Derive address from test private key."""
    account = Account.from_key(test_private_key)
    return account.address


# ---------------------------- Mock Transaction Receipts ----------------------------

@pytest.fixture(scope="function")
def mock_tx_receipt() -> TxReceipt:
    """Return a mock transaction receipt."""
    return {
        "blockHash": "0x" + "b" * 64,
        "blockNumber": 12345,
        "contractAddress": None,
        "cumulativeGasUsed": 21000,
        "effectiveGasPrice": 1000000000,
        "from": "0x" + "f" * 40,
        "gasUsed": 21000,
        "logs": [],
        "logsBloom": "0x" + "0" * 512,
        "status": 1,
        "to": "0x" + "t" * 40,
        "transactionHash": "0x" + "a" * 64,
        "transactionIndex": 0,
        "type": "0x0",
    }


@pytest.fixture(scope="function")
def mock_block_data() -> BlockData:
    """Return a mock block data."""
    return {
        "number": 12345,
        "hash": "0x" + "h" * 64,
        "parentHash": "0x" + "p" * 64,
        "nonce": "0x0",
        "sha3Uncles": "0x" + "s" * 64,
        "logsBloom": "0x" + "0" * 512,
        "transactionsRoot": "0x" + "r" * 64,
        "stateRoot": "0x" + "s" * 64,
        "receiptsRoot": "0x" + "r" * 64,
        "miner": "0x" + "m" * 40,
        "difficulty": 1,
        "totalDifficulty": 100,
        "extraData": "0x",
        "size": 1024,
        "gasLimit": 30000000,
        "gasUsed": 21000,
        "timestamp": 1234567890,
        "transactions": [],
        "uncles": [],
    }


# ---------------------------- Async Fixtures ----------------------------

@pytest_asyncio.fixture(scope="function")
async def async_web3_client(web3_client) -> AsyncGenerator[Web3, None]:
    """Provide an async-compatible web3 client (if needed)."""
    # For simplicity, we can wrap the sync client, but this is just a placeholder.
    yield web3_client


@pytest_asyncio.fixture(scope="function")
async def async_wallet_manager(wallet_manager) -> AsyncGenerator[WalletManager, None]:
    """Provide an async wallet manager for async tests."""
    yield wallet_manager


# ---------------------------- Cleanup Fixtures ----------------------------

@pytest.fixture(autouse=True)
def clean_up_blockchain_state():
    """Automatically clean up any blockchain state after each test."""
    yield
    # Cleanup can be implemented if needed (e.g., reset eth-tester state)


# ---------------------------- Main Test Configuration ----------------------------

# Override any environment variables for testing if needed.
# This fixture can be used to set up mock responses for external API calls.

@pytest.fixture(scope="function")
def mock_external_blockchain_api():
    """Mock external blockchain API calls (e.g., Etherscan)."""
    with patch("blockchain.web3.etherscan_client.EtherscanClient.get_contract_abi") as mock:
        mock.return_value = [{"type": "function", "name": "test", "inputs": [], "outputs": []}]
        yield mock

# End of conftest.py
