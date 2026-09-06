# tests/blockchain/test_smart_contracts.py
"""
Smart Contract Tests for the NEXUS AI Trading System.

This module contains comprehensive tests for smart contract management:
- ContractManager: deployment, interaction, upgrades
- Contract auditing and verification
- ERC20, ERC721, ERC1155 contract implementations
- Proxy patterns (transparent, UUPS, beacon)
- Multi-sig wallet contracts
- Contract event handling and monitoring
- ABI management and validation
- Contract compilation and deployment scripts

All tests use mocked web3 providers and contract interactions.
"""

import asyncio
import json
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from eth_account import Account

from blockchain.smart_contracts.base_contract import BaseContract
from blockchain.smart_contracts.contract_manager import ContractManager
from blockchain.smart_contracts.contract_abi import ContractABI
from blockchain.smart_contracts.contract_audit import ContractAuditor
from blockchain.smart_contracts.contract_bytecode import ContractBytecodeManager
from blockchain.smart_contracts.contract_compiler import ContractCompiler
from blockchain.smart_contracts.contract_config import ContractConfig
from blockchain.smart_contracts.contract_deployer import ContractDeployer
from blockchain.smart_contracts.contract_interceptor import ContractInterceptor
from blockchain.smart_contracts.contract_upgrade import ContractUpgradeManager
from blockchain.smart_contracts.contract_verifier import ContractVerifier
from blockchain.smart_contracts.erc20_contract import ERC20Contract
from blockchain.smart_contracts.erc721_contract import ERC721Contract
from blockchain.smart_contracts.erc1155_contract import ERC1155Contract
from blockchain.smart_contracts.aave_contract import AaveContract
from blockchain.smart_contracts.compound_contract import CompoundContract
from blockchain.smart_contracts.uniswap_contract import UniswapContract
from blockchain.smart_contracts.pancake_contract import PancakeContract

pytest_plugins = ["tests.blockchain.conftest"]


# ============================== BASE CONTRACT TESTS ==============================

class TestBaseContract:
    """Test the BaseContract abstract class."""

    def test_base_contract_initialization(self):
        """Test initializing a base contract."""
        contract = BaseContract(
            name="TestContract",
            address="0x" + "a" * 40,
            abi=[],
            chain_id=1,
        )
        assert contract.name == "TestContract"
        assert contract.address == "0x" + "a" * 40
        assert contract.chain_id == 1

    def test_get_contract_info(self):
        """Test getting contract information."""
        contract = BaseContract(name="Test", address="0x123", abi=[], chain_id=1)
        info = contract.get_contract_info()
        assert info["name"] == "Test"
        assert info["address"] == "0x123"
        assert info["chain_id"] == 1

    async def test_call_function_not_implemented(self):
        """Test that call_function raises NotImplementedError."""
        contract = BaseContract(name="Test", address="0x123", abi=[], chain_id=1)
        with pytest.raises(NotImplementedError):
            await contract.call_function("balanceOf", ["0x123"])

    async def test_send_transaction_not_implemented(self):
        """Test that send_transaction raises NotImplementedError."""
        contract = BaseContract(name="Test", address="0x123", abi=[], chain_id=1)
        with pytest.raises(NotImplementedError):
            await contract.send_transaction("transfer", ["0x123", 100], "0xkey", "0xfrom")


# ============================== ERC20 CONTRACT TESTS ==============================

class TestERC20Contract:
    """Test the ERC20Contract implementation."""

    @pytest.fixture
    def erc20_contract(self, web3_client_service, mock_erc20_contract):
        """Return an ERC20Contract instance with mocked contract."""
        contract = ERC20Contract(
            name="TestToken",
            address="0x" + "b" * 40,
            abi=[],
            chain_id=1,
            web3_client=web3_client_service,
        )
        contract.contract = mock_erc20_contract
        return contract

    async def test_get_name(self, erc20_contract):
        """Test getting token name."""
        with patch.object(erc20_contract.contract.functions, "name") as mock_name:
            mock_name.return_value.call.return_value = "Test Token"
            name = await erc20_contract.get_name()
            assert name == "Test Token"

    async def test_get_symbol(self, erc20_contract):
        """Test getting token symbol."""
        with patch.object(erc20_contract.contract.functions, "symbol") as mock_symbol:
            mock_symbol.return_value.call.return_value = "TT"
            symbol = await erc20_contract.get_symbol()
            assert symbol == "TT"

    async def test_get_decimals(self, erc20_contract):
        """Test getting token decimals."""
        with patch.object(erc20_contract.contract.functions, "decimals") as mock_dec:
            mock_dec.return_value.call.return_value = 18
            decimals = await erc20_contract.get_decimals()
            assert decimals == 18

    async def test_get_total_supply(self, erc20_contract):
        """Test getting total supply."""
        with patch.object(erc20_contract.contract.functions, "totalSupply") as mock_supply:
            mock_supply.return_value.call.return_value = 10**6 * 10**18
            supply = await erc20_contract.get_total_supply()
            assert supply == 10**6 * 10**18

    async def test_get_balance(self, erc20_contract):
        """Test getting balance of an address."""
        with patch.object(erc20_contract.contract.functions, "balanceOf") as mock_balance:
            mock_balance.return_value.call.return_value = 1000
            balance = await erc20_contract.get_balance("0xowner")
            assert balance == 1000

    async def test_transfer(self, erc20_contract, test_private_key, test_address_from_private_key):
        """Test transferring tokens."""
        with patch.object(erc20_contract.contract.functions, "transfer") as mock_transfer:
            mock_transfer.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc20_contract.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "c" * 64
                with patch.object(erc20_contract.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "c" * 64}
                    result = await erc20_contract.transfer(
                        to="0x" + "d" * 40,
                        amount=100,
                        private_key=test_private_key,
                        from_address=test_address_from_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "c" * 64

    async def test_approve(self, erc20_contract, test_private_key, test_address_from_private_key):
        """Test approving a spender."""
        with patch.object(erc20_contract.contract.functions, "approve") as mock_approve:
            mock_approve.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc20_contract.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "e" * 64
                with patch.object(erc20_contract.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "e" * 64}
                    result = await erc20_contract.approve(
                        spender="0x" + "f" * 40,
                        amount=1000,
                        private_key=test_private_key,
                        from_address=test_address_from_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "e" * 64

    async def test_allowance(self, erc20_contract):
        """Test getting allowance."""
        with patch.object(erc20_contract.contract.functions, "allowance") as mock_allowance:
            mock_allowance.return_value.call.return_value = 500
            allowance = await erc20_contract.get_allowance("0xowner", "0xspender")
            assert allowance == 500

    async def test_transfer_from(self, erc20_contract, test_private_key, test_address_from_private_key):
        """Test transferFrom (allowance-based)."""
        with patch.object(erc20_contract.contract.functions, "transferFrom") as mock_transfer_from:
            mock_transfer_from.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc20_contract.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "g" * 64
                with patch.object(erc20_contract.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "g" * 64}
                    result = await erc20_contract.transfer_from(
                        from_address="0x" + "h" * 40,
                        to_address="0x" + "i" * 40,
                        amount=50,
                        private_key=test_private_key,
                        spender_address=test_address_from_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "g" * 64


# ============================== ERC721 CONTRACT TESTS ==============================

class TestERC721Contract:
    """Test the ERC721Contract implementation."""

    @pytest.fixture
    def erc721_contract(self, web3_client_service, mock_erc721_contract):
        """Return an ERC721Contract instance."""
        contract = ERC721Contract(
            name="TestNFT",
            address="0x" + "j" * 40,
            abi=[],
            chain_id=1,
            web3_client=web3_client_service,
        )
        contract.contract = mock_erc721_contract
        return contract

    async def test_get_name(self, erc721_contract):
        """Test getting collection name."""
        with patch.object(erc721_contract.contract.functions, "name") as mock_name:
            mock_name.return_value.call.return_value = "Test NFT"
            name = await erc721_contract.get_name()
            assert name == "Test NFT"

    async def test_get_symbol(self, erc721_contract):
        """Test getting collection symbol."""
        with patch.object(erc721_contract.contract.functions, "symbol") as mock_symbol:
            mock_symbol.return_value.call.return_value = "TNFT"
            symbol = await erc721_contract.get_symbol()
            assert symbol == "TNFT"

    async def test_token_uri(self, erc721_contract):
        """Test getting token URI."""
        with patch.object(erc721_contract.contract.functions, "tokenURI") as mock_uri:
            mock_uri.return_value.call.return_value = "ipfs://Qm123"
            uri = await erc721_contract.get_token_uri(1)
            assert uri == "ipfs://Qm123"

    async def test_owner_of(self, erc721_contract):
        """Test getting owner of a token."""
        with patch.object(erc721_contract.contract.functions, "ownerOf") as mock_owner:
            mock_owner.return_value.call.return_value = "0x" + "k" * 40
            owner = await erc721_contract.owner_of(1)
            assert owner == "0x" + "k" * 40

    async def test_transfer(self, erc721_contract, test_private_key, test_address_from_private_key):
        """Test transferring NFT."""
        with patch.object(erc721_contract.contract.functions, "safeTransferFrom") as mock_transfer:
            mock_transfer.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc721_contract.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "l" * 64
                with patch.object(erc721_contract.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "l" * 64}
                    result = await erc721_contract.transfer(
                        token_id=1,
                        from_address=test_address_from_private_key,
                        to_address="0x" + "m" * 40,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "l" * 64

    async def test_approve(self, erc721_contract, test_private_key, test_address_from_private_key):
        """Test approving an operator for a token."""
        with patch.object(erc721_contract.contract.functions, "approve") as mock_approve:
            mock_approve.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc721_contract.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "n" * 64
                with patch.object(erc721_contract.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "n" * 64}
                    result = await erc721_contract.approve(
                        token_id=1,
                        operator="0x" + "o" * 40,
                        private_key=test_private_key,
                        from_address=test_address_from_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "n" * 64


# ============================== ERC1155 CONTRACT TESTS ==============================

class TestERC1155Contract:
    """Test the ERC1155Contract implementation."""

    @pytest.fixture
    def erc1155_contract(self, web3_client_service):
        """Return an ERC1155Contract instance."""
        contract = ERC1155Contract(
            name="TestMulti",
            address="0x" + "p" * 40,
            abi=[],
            chain_id=1,
            web3_client=web3_client_service,
        )
        contract.contract = MagicMock()
        return contract

    async def test_uri(self, erc1155_contract):
        """Test getting URI for a token type."""
        with patch.object(erc1155_contract.contract.functions, "uri") as mock_uri:
            mock_uri.return_value.call.return_value = "ipfs://Qm456/{id}"
            uri = await erc1155_contract.get_uri(1)
            assert uri == "ipfs://Qm456/{id}"

    async def test_balance_of(self, erc1155_contract):
        """Test getting balance for a token type."""
        with patch.object(erc1155_contract.contract.functions, "balanceOf") as mock_balance:
            mock_balance.return_value.call.return_value = 5
            balance = await erc1155_contract.get_balance("0xowner", 1)
            assert balance == 5


# ============================== CONTRACT DEPLOYER TESTS ==============================

class TestContractDeployer:
    """Test the ContractDeployer for deploying contracts."""

    @pytest.fixture
    def contract_deployer(self, web3_client_service, test_private_key, test_address_from_private_key):
        """Return a ContractDeployer instance."""
        return ContractDeployer(
            web3_client=web3_client_service,
            default_private_key=test_private_key,
            default_from_address=test_address_from_private_key,
        )

    async def test_deploy_erc20(self, contract_deployer):
        """Test deploying an ERC20 contract."""
        # Mock the deployment
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "q" * 40
        mock_contract.constructor.return_value.transact.return_value = {"transactionHash": "0x" + "r" * 64}

        with patch("web3.eth.contract", return_value=mock_contract) as mock_eth_contract:
            with patch.object(contract_deployer.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                mock_wait.return_value = {"status": 1, "contractAddress": mock_contract.address}
                address = await contract_deployer.deploy_erc20(
                    name="TestToken",
                    symbol="TT",
                    decimals=18,
                    initial_supply=10**6,
                )
                assert address == mock_contract.address
                mock_eth_contract.assert_called_once()
                mock_wait.assert_called_once()

    async def test_deploy_erc721(self, contract_deployer):
        """Test deploying an ERC721 contract."""
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "s" * 40
        mock_contract.constructor.return_value.transact.return_value = {"transactionHash": "0x" + "t" * 64}

        with patch("web3.eth.contract", return_value=mock_contract) as mock_eth_contract:
            with patch.object(contract_deployer.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                mock_wait.return_value = {"status": 1, "contractAddress": mock_contract.address}
                address = await contract_deployer.deploy_erc721(
                    name="TestNFT",
                    symbol="TNFT",
                )
                assert address == mock_contract.address

    async def test_deploy_upgradeable_proxy(self, contract_deployer):
        """Test deploying an upgradeable contract with proxy."""
        # Mock proxy deployment
        mock_impl = MagicMock()
        mock_impl.address = "0x" + "u" * 40
        mock_proxy = MagicMock()
        mock_proxy.address = "0x" + "v" * 40

        with patch.object(contract_deployer, "deploy_contract") as mock_deploy:
            mock_deploy.side_effect = [mock_impl.address, mock_proxy.address]
            with patch.object(contract_deployer, "_initialize_proxy") as mock_init:
                mock_init.return_value = {"tx_hash": "0x" + "w" * 64}
                result = await contract_deployer.deploy_upgradeable_proxy(
                    implementation_bytecode="0x60806040",
                    initializer_data="0x",
                    proxy_bytecode="0x60806040",
                )
                assert result["implementation"] == mock_impl.address
                assert result["proxy"] == mock_proxy.address

    async def test_deploy_with_constructor_args(self, contract_deployer):
        """Test deploying with constructor arguments."""
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "x" * 40
        mock_contract.constructor.return_value.transact.return_value = {"transactionHash": "0x" + "y" * 64}

        with patch("web3.eth.contract", return_value=mock_contract) as mock_eth_contract:
            with patch.object(contract_deployer.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                mock_wait.return_value = {"status": 1, "contractAddress": mock_contract.address}
                address = await contract_deployer.deploy_contract(
                    abi=[],
                    bytecode="0x60806040",
                    constructor_args=[1, "test"],
                )
                assert address == mock_contract.address
                # Verify that constructor was called with args
                mock_contract.constructor.assert_called_once_with(1, "test")


# ============================== CONTRACT UPGRADE MANAGER TESTS ==============================

class TestContractUpgradeManager:
    """Test the ContractUpgradeManager for upgrading contracts."""

    @pytest.fixture
    def upgrade_manager(self, web3_client_service, test_private_key, test_address_from_private_key):
        """Return a ContractUpgradeManager instance."""
        return ContractUpgradeManager(
            web3_client=web3_client_service,
            default_private_key=test_private_key,
            default_from_address=test_address_from_private_key,
        )

    async def test_upgrade_proxy(self, upgrade_manager):
        """Test upgrading a proxy contract."""
        mock_proxy = MagicMock()
        mock_proxy.functions.upgradeTo.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}

        with patch.object(upgrade_manager.web3_client.eth, "contract") as mock_contract:
            mock_contract.return_value = mock_proxy
            with patch.object(upgrade_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "z" * 64
                with patch.object(upgrade_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "z" * 64}
                    result = await upgrade_manager.upgrade_proxy(
                        proxy_address="0x" + "aa" * 40,
                        new_implementation="0x" + "bb" * 40,
                    )
                    assert result["tx_hash"] == "0x" + "z" * 64
                    mock_proxy.functions.upgradeTo.assert_called_once_with("0x" + "bb" * 40)

    async def test_upgrade_with_transparent_proxy(self, upgrade_manager):
        """Test upgrading via transparent proxy pattern."""
        # Transparent proxy uses admin address
        mock_proxy = MagicMock()
        mock_admin = MagicMock()
        mock_admin.functions.upgrade.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}

        with patch.object(upgrade_manager.web3_client.eth, "contract") as mock_contract:
            mock_contract.side_effect = [mock_admin, mock_proxy]
            with patch.object(upgrade_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "cc" * 32
                with patch.object(upgrade_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "cc" * 32}
                    result = await upgrade_manager.upgrade_proxy(
                        proxy_address="0x" + "aa" * 40,
                        new_implementation="0x" + "bb" * 40,
                        proxy_type="transparent",
                        admin_address="0x" + "dd" * 40,
                    )
                    assert result["tx_hash"] == "0x" + "cc" * 32


# ============================== CONTRACT AUDITOR TESTS ==============================

class TestContractAuditor:
    """Test the ContractAuditor for auditing contracts."""

    @pytest.fixture
    def contract_auditor(self):
        """Return a ContractAuditor instance."""
        return ContractAuditor()

    async def test_audit_contract(self, contract_auditor):
        """Test auditing a contract."""
        # Mock static analysis results
        with patch.object(contract_auditor, "_run_static_analysis") as mock_static:
            mock_static.return_value = {"issues": [], "score": 95}
            with patch.object(contract_auditor, "_run_dynamic_analysis") as mock_dynamic:
                mock_dynamic.return_value = {"passed": True}
                with patch.object(contract_auditor, "_check_known_vulnerabilities") as mock_vuln:
                    mock_vuln.return_value = []
                    report = await contract_auditor.audit_contract(
                        bytecode="0x60806040",
                        abi=[],
                        source_code=None,
                    )
                    assert report["static_score"] == 95
                    assert report["vulnerabilities"] == []
                    assert report["overall_score"] > 0

    async def test_check_erc20_compliance(self, contract_auditor):
        """Test checking ERC20 compliance."""
        abi = [
            {"type": "function", "name": "transfer", "inputs": [{"type": "address"}, {"type": "uint256"}]},
            {"type": "function", "name": "balanceOf", "inputs": [{"type": "address"}]},
            # Missing approve and allowance
        ]
        compliance = await contract_auditor.check_erc20_compliance(abi)
        assert compliance["is_compliant"] is False
        assert "missing functions" in compliance["issues"][0].lower()


# ============================== CONTRACT COMPILER TESTS ==============================

class TestContractCompiler:
    """Test the ContractCompiler for compiling Solidity contracts."""

    @pytest.fixture
    def contract_compiler(self):
        """Return a ContractCompiler instance."""
        return ContractCompiler()

    async def test_compile_solidity(self, contract_compiler):
        """Test compiling a Solidity source."""
        source = """
        pragma solidity ^0.8.0;
        contract Test {
            uint256 public value;
            constructor(uint256 _value) { value = _value; }
        }
        """
        with patch.object(contract_compiler, "_run_solc") as mock_solc:
            mock_solc.return_value = {
                "contracts": {
                    "Test": {
                        "abi": [],
                        "evm": {"bytecode": {"object": "0x60806040"}},
                    }
                }
            }
            result = await contract_compiler.compile_contract(source)
            assert "Test" in result["contracts"]
            assert result["contracts"]["Test"]["bytecode"] == "0x60806040"

    async def test_compile_with_imports(self, contract_compiler):
        """Test compiling with imports."""
        source = """
        import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
        contract MyToken is ERC20 {}
        """
        # Mock the import resolution
        with patch.object(contract_compiler, "_resolve_imports") as mock_imports:
            mock_imports.return_value = {"@openzeppelin/...": "pragma solidity ^0.8.0;"}
            with patch.object(contract_compiler, "_run_solc") as mock_solc:
                mock_solc.return_value = {"contracts": {"MyToken": {"abi": [], "evm": {"bytecode": {"object": "0x"}}}}
                result = await contract_compiler.compile_contract(source)
                assert "MyToken" in result["contracts"]


# ============================== CONTRACT VERIFIER TESTS ==============================

class TestContractVerifier:
    """Test the ContractVerifier for verifying contracts on Etherscan."""

    @pytest.fixture
    def contract_verifier(self):
        """Return a ContractVerifier instance."""
        return ContractVerifier()

    async def test_verify_contract(self, contract_verifier):
        """Test verifying a contract."""
        with patch.object(contract_verifier, "_call_etherscan_api") as mock_api:
            mock_api.return_value = {"status": "1", "message": "OK", "result": "0x" + "aa" * 40}
            result = await contract_verifier.verify_contract(
                address="0x" + "bb" * 40,
                bytecode="0x60806040",
                source_code="pragma solidity ^0.8.0; contract Test {}",
                compiler_version="v0.8.0",
            )
            assert result["status"] == "verified"

    async def test_verify_contract_failure(self, contract_verifier):
        """Test verification failure."""
        with patch.object(contract_verifier, "_call_etherscan_api") as mock_api:
            mock_api.return_value = {"status": "0", "message": "Fail", "result": ""}
            result = await contract_verifier.verify_contract(
                address="0x" + "cc" * 40,
                bytecode="0x",
                source_code="",
            )
            assert result["status"] == "failed"


# ============================== CONTRACT INTERCEPTOR TESTS ==============================

class TestContractInterceptor:
    """Test the ContractInterceptor for logging/intercepting contract calls."""

    @pytest.fixture
    def contract_interceptor(self):
        """Return a ContractInterceptor instance."""
        return ContractInterceptor()

    async def test_intercept_call(self, contract_interceptor):
        """Test intercepting a contract call."""
        # Set up a mock contract
        mock_contract = MagicMock()
        mock_contract.functions.transfer.return_value.call.return_value = True

        # Intercept and log
        with patch.object(contract_interceptor, "_log_interaction") as mock_log:
            result = await contract_interceptor.intercept_call(
                contract=mock_contract,
                function_name="transfer",
                args=["0x123", 100],
            )
            assert result is True
            mock_log.assert_called_once_with("transfer", args=["0x123", 100], result=True)

    async def test_intercept_transaction(self, contract_interceptor):
        """Test intercepting a transaction."""
        mock_contract = MagicMock()
        mock_contract.functions.transfer.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}

        with patch.object(contract_interceptor, "_log_interaction") as mock_log:
            with patch.object(contract_interceptor.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "dd" * 32
                tx_hash = await contract_interceptor.intercept_transaction(
                    contract=mock_contract,
                    function_name="transfer",
                    args=["0x123", 100],
                    private_key="0xkey",
                    from_address="0xfrom",
                )
                assert tx_hash == "0x" + "dd" * 32
                mock_log.assert_called_once()


# ============================== CONTRACT MANAGER TESTS ==============================

class TestContractManager:
    """Test the ContractManager orchestrating all contract operations."""

    @pytest.fixture
    def contract_manager(self, web3_client_service, test_private_key, test_address_from_private_key):
        """Return a ContractManager instance."""
        return ContractManager(
            web3_client=web3_client_service,
            default_private_key=test_private_key,
            default_from_address=test_address_from_private_key,
        )

    async def test_register_contract(self, contract_manager):
        """Test registering a contract."""
        await contract_manager.register_contract(
            name="TestToken",
            address="0x" + "ee" * 40,
            abi=[],
            chain_id=1,
        )
        assert "TestToken" in contract_manager.contracts

    async def test_get_contract(self, contract_manager):
        """Test getting a registered contract."""
        await contract_manager.register_contract(
            name="TestToken",
            address="0x" + "ff" * 40,
            abi=[],
            chain_id=1,
        )
        contract = await contract_manager.get_contract("TestToken")
        assert contract.name == "TestToken"

    async def test_call_contract_function(self, contract_manager):
        """Test calling a function on a registered contract."""
        # Register a mock contract
        mock_contract = AsyncMock()
        mock_contract.call_function = AsyncMock(return_value=100)

        with patch.object(contract_manager, "get_contract", return_value=mock_contract):
            result = await contract_manager.call_contract_function(
                contract_name="TestToken",
                function_name="balanceOf",
                args=["0xowner"],
            )
            assert result == 100
            mock_contract.call_function.assert_called_once_with("balanceOf", ["0xowner"])

    async def test_deploy_and_register(self, contract_manager):
        """Test deploying a contract and registering it automatically."""
        with patch.object(contract_manager.deployer, "deploy_erc20") as mock_deploy:
            mock_deploy.return_value = "0x" + "gg" * 40
            with patch.object(contract_manager, "register_contract") as mock_register:
                address = await contract_manager.deploy_and_register(
                    contract_type="erc20",
                    name="MyToken",
                    symbol="MT",
                    decimals=18,
                    initial_supply=1000,
                )
                assert address == "0x" + "gg" * 40
                mock_register.assert_called_once()

    async def test_upgrade_contract(self, contract_manager):
        """Test upgrading a contract via manager."""
        with patch.object(contract_manager.upgrade_manager, "upgrade_proxy") as mock_upgrade:
            mock_upgrade.return_value = {"tx_hash": "0x" + "hh" * 32}
            result = await contract_manager.upgrade_contract(
                contract_name="TestToken",
                new_implementation="0x" + "ii" * 40,
            )
            assert result["tx_hash"] == "0x" + "hh" * 32


# ============================== PROTOCOL CONTRACT TESTS ==============================

class TestProtocolContracts:
    """Test specific protocol contract wrappers (Aave, Compound, Uniswap)."""

    @pytest.fixture
    def aave_contract(self, web3_client_service, mock_aave_contract):
        """Return an AaveContract instance."""
        contract = AaveContract(
            name="Aave",
            address="0x" + "jj" * 40,
            abi=[],
            chain_id=1,
            web3_client=web3_client_service,
        )
        contract.contract = mock_aave_contract
        return contract

    @pytest.fixture
    def compound_contract(self, web3_client_service):
        """Return a CompoundContract instance."""
        contract = CompoundContract(
            name="Compound",
            address="0x" + "kk" * 40,
            abi=[],
            chain_id=1,
            web3_client=web3_client_service,
        )
        contract.contract = MagicMock()
        return contract

    @pytest.fixture
    def uniswap_contract(self, web3_client_service, mock_uniswap_contract):
        """Return a UniswapContract instance."""
        contract = UniswapContract(
            name="Uniswap",
            address="0x" + "ll" * 40,
            abi=[],
            chain_id=1,
            web3_client=web3_client_service,
        )
        contract.contract = mock_uniswap_contract
        return contract

    async def test_aave_deposit(self, aave_contract, test_private_key, test_address_from_private_key):
        """Test Aave deposit function."""
        with patch.object(aave_contract.contract.functions, "deposit") as mock_deposit:
            mock_deposit.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(aave_contract.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "mm" * 32
                with patch.object(aave_contract.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "mm" * 32}
                    result = await aave_contract.deposit(
                        asset="0xUSDC",
                        amount=100,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "mm" * 32

    async def test_compound_supply(self, compound_contract, test_private_key, test_address_from_private_key):
        """Test Compound supply function."""
        with patch.object(compound_contract.contract.functions, "mint") as mock_mint:
            mock_mint.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(compound_contract.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "nn" * 32
                with patch.object(compound_contract.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "nn" * 32}
                    result = await compound_contract.supply(
                        asset="USDC",
                        amount=100,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "nn" * 32

    async def test_uniswap_swap(self, uniswap_contract, test_private_key, test_address_from_private_key):
        """Test Uniswap swap function."""
        with patch.object(uniswap_contract.contract.functions, "swapExactTokensForTokens") as mock_swap:
            mock_swap.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(uniswap_contract.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "oo" * 32
                with patch.object(uniswap_contract.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "oo" * 32}
                    result = await uniswap_contract.swap(
                        token_in="0xUSDC",
                        token_out="0xWETH",
                        amount_in=100,
                        min_amount_out=0.09,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "oo" * 32


# ============================== CONFIGURATION TESTS ==============================

class TestContractConfig:
    """Test contract configuration and network settings."""

    def test_contract_config_load(self):
        """Test loading contract configuration."""
        config = ContractConfig()
        config.load_from_file("path/to/config.json")
        # Mock the file load
        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "chain_id": 1,
                "contracts": {
                    "TestToken": {"address": "0x123", "abi": []}
                }
            })
            config.load_from_file("config.json")
            assert config.chain_id == 1
            assert "TestToken" in config.contracts

    def test_get_contract_config(self, contract_config):
        """Test retrieving configuration for a contract."""
        config = ContractConfig()
        config.contracts = {"TestToken": {"address": "0x123", "abi": []}}
        contract_cfg = config.get_contract_config("TestToken")
        assert contract_cfg["address"] == "0x123"


# ============================== INTEGRATION TESTS ==============================

class TestSmartContractIntegration:
    """Integration tests for smart contract components."""

    async def test_full_erc20_lifecycle(
        self,
        contract_deployer,
        contract_manager,
        test_private_key,
        test_address_from_private_key,
    ):
        """Test a complete ERC20 lifecycle: deploy, mint, transfer, approve, transferFrom."""
        # 1. Deploy ERC20
        with patch.object(contract_deployer, "deploy_erc20") as mock_deploy:
            mock_deploy.return_value = "0x" + "pp" * 40
            token_address = await contract_deployer.deploy_erc20(
                name="LifecycleToken",
                symbol="LT",
                decimals=18,
                initial_supply=1000,
            )
            assert token_address == "0x" + "pp" * 40

        # 2. Register contract
        await contract_manager.register_contract(
            name="LifecycleToken",
            address=token_address,
            abi=[],  # real abi would be loaded
            chain_id=1,
        )

        # 3. Get balance
        token_contract = await contract_manager.get_contract("LifecycleToken")
        with patch.object(token_contract, "call_function") as mock_call:
            mock_call.return_value = 1000
            balance = await token_contract.call_function("balanceOf", [test_address_from_private_key])
            assert balance == 1000

        # 4. Transfer
        with patch.object(token_contract, "send_transaction") as mock_send:
            mock_send.return_value = {"tx_hash": "0x" + "qq" * 32}
            result = await token_contract.send_transaction(
                "transfer",
                ["0x" + "rr" * 40, 500],
                test_private_key,
                test_address_from_private_key,
            )
            assert result["tx_hash"] == "0x" + "qq" * 32

        # 5. Approve
        with patch.object(token_contract, "send_transaction") as mock_approve:
            mock_approve.return_value = {"tx_hash": "0x" + "ss" * 32}
            result = await token_contract.send_transaction(
                "approve",
                ["0x" + "tt" * 40, 200],
                test_private_key,
                test_address_from_private_key,
            )
            assert result["tx_hash"] == "0x" + "ss" * 32

        # 6. TransferFrom
        with patch.object(token_contract, "send_transaction") as mock_transfer_from:
            mock_transfer_from.return_value = {"tx_hash": "0x" + "uu" * 32}
            result = await token_contract.send_transaction(
                "transferFrom",
                [test_address_from_private_key, "0x" + "vv" * 40, 100],
                test_private_key,
                test_address_from_private_key,
            )
            assert result["tx_hash"] == "0x" + "uu" * 32

    async def test_upgradeable_contract_flow(self, contract_deployer, upgrade_manager):
        """Test deploying and upgrading a contract."""
        # Deploy implementation
        impl_address = "0x" + "ww" * 40
        with patch.object(contract_deployer, "deploy_contract") as mock_deploy:
            mock_deploy.return_value = impl_address
            deployed = await contract_deployer.deploy_contract(abi=[], bytecode="0x")
            assert deployed == impl_address

        # Deploy proxy pointing to implementation
        proxy_address = "0x" + "xx" * 40
        with patch.object(contract_deployer, "deploy_contract") as mock_deploy_proxy:
            mock_deploy_proxy.return_value = proxy_address
            proxy = await contract_deployer.deploy_contract(abi=[], bytecode="0x")
            assert proxy == proxy_address

        # Upgrade to new implementation
        new_impl = "0x" + "yy" * 40
        with patch.object(upgrade_manager, "upgrade_proxy") as mock_upgrade:
            mock_upgrade.return_value = {"tx_hash": "0x" + "zz" * 32}
            result = await upgrade_manager.upgrade_proxy(proxy_address, new_impl)
            assert result["tx_hash"] == "0x" + "zz" * 32

    async def test_multi_sig_contract(self, contract_manager):
        """Test multi-sig wallet contract operations."""
        # Deploy multi-sig
        # We'll mock the deployment and then test the confirmation flow
        multi_sig_abi = []  # simplified
        multi_sig_address = "0x" + "aaa" * 40

        # Register
        await contract_manager.register_contract(
            name="MultiSig",
            address=multi_sig_address,
            abi=multi_sig_abi,
            chain_id=1,
        )

        multi_sig = await contract_manager.get_contract("MultiSig")

        # Submit transaction
        with patch.object(multi_sig, "send_transaction") as mock_submit:
            mock_submit.return_value = {"tx_hash": "0x" + "bbb" * 32}
            result = await multi_sig.send_transaction(
                "submitTransaction",
                ["0x" + "ccc" * 40, 100, "0x"],
                "0xkey1",
                "0xaddr1",
            )
            assert result["tx_hash"] == "0x" + "bbb" * 32

        # Confirm transaction
        with patch.object(multi_sig, "send_transaction") as mock_confirm:
            mock_confirm.return_value = {"tx_hash": "0x" + "ddd" * 32}
            result = await multi_sig.send_transaction(
                "confirmTransaction",
                [1],
                "0xkey2",
                "0xaddr2",
            )
            assert result["tx_hash"] == "0x" + "ddd" * 32

        # Execute after enough confirmations
        with patch.object(multi_sig, "send_transaction") as mock_execute:
            mock_execute.return_value = {"tx_hash": "0x" + "eee" * 32}
            result = await multi_sig.send_transaction(
                "executeTransaction",
                [1],
                "0xkey3",
                "0xaddr3",
            )
            assert result["tx_hash"] == "0x" + "eee" * 32

    async def test_contract_event_listening(self, contract_manager):
        """Test listening for contract events."""
        # Register a contract with events
        event_abi = [
            {"type": "event", "name": "Transfer", "inputs": [{"indexed": True, "type": "address"}, {"indexed": True, "type": "address"}, {"type": "uint256"}]}
        ]
        contract_address = "0x" + "fff" * 40
        await contract_manager.register_contract(
            name="EventToken",
            address=contract_address,
            abi=event_abi,
            chain_id=1,
        )

        contract = await contract_manager.get_contract("EventToken")

        # Set up event filter
        with patch.object(contract, "get_contract_events") as mock_events:
            mock_events.return_value = [
                {"event": "Transfer", "args": {"from": "0xfrom", "to": "0xto", "value": 100}},
                {"event": "Transfer", "args": {"from": "0xfrom2", "to": "0xto2", "value": 200}},
            ]
            events = await contract.get_contract_events(
                event_name="Transfer",
                from_block=0,
                to_block="latest",
            )
            assert len(events) == 2
            assert events[0]["event"] == "Transfer"
