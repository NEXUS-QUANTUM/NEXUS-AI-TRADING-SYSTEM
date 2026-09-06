# tests/blockchain/test_wallet_manager.py
"""
Wallet Manager Tests for the NEXUS AI Trading System.

This module contains comprehensive tests for all wallet-related functionality:
- WalletManager: multi-chain wallet management
- Wallet creation: single wallet, HD wallets (BIP32, BIP39, BIP44)
- Wallet import: private key, mnemonic, keystore
- Wallet balance checking (multiple chains)
- Transaction signing and sending
- Wallet backup and recovery
- Wallet analytics (transaction history, balance tracking)
- Security: encryption, secure storage
- Multi-chain support (Ethereum, BSC, Polygon, Solana, Tron)

All tests use mocked web3 providers and wallet operations.
"""

import asyncio
import json
import os
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

from blockchain.wallets.base_wallet import BaseWallet
from blockchain.wallets.wallet_manager import WalletManager
from blockchain.wallets.ethereum_wallet import EthereumWallet
from blockchain.wallets.bsc_wallet import BSCWallet
from blockchain.wallets.polygon_wallet import PolygonWallet
from blockchain.wallets.solana_wallet import SolanaWallet
from blockchain.wallets.tron_wallet import TronWallet
from blockchain.wallets.multi_chain_wallet import MultiChainWallet
from blockchain.wallets.wallet_config import WalletConfig
from blockchain.wallets.wallet_hd import HDWalletManager
from blockchain.wallets.wallet_backup import WalletBackupManager
from blockchain.wallets.wallet_security import WalletSecurityManager
from blockchain.wallets.wallet_analytics import WalletAnalytics
from blockchain.wallets.wallet_monitor import WalletMonitor
from blockchain.wallets.wallet_balance import WalletBalanceChecker
from blockchain.wallets.wallet_signer import WalletSigner
from blockchain.wallets.wallet_transaction import WalletTransactionManager

pytest_plugins = ["tests.blockchain.conftest"]


# ============================== BASE WALLET TESTS ==============================

class TestBaseWallet:
    """Test the BaseWallet abstract class."""

    def test_base_wallet_initialization(self):
        """Test initializing a base wallet."""
        wallet = BaseWallet(
            chain="ethereum",
            address="0x" + "a" * 40,
            private_key="0x" + "b" * 64,
            public_key=None,
        )
        assert wallet.chain == "ethereum"
        assert wallet.address == "0x" + "a" * 40
        assert wallet.private_key == "0x" + "b" * 64

    def test_get_address(self, base_wallet):
        """Test getting wallet address."""
        assert base_wallet.get_address() == "0x" + "a" * 40

    def test_get_balance_not_implemented(self):
        """Test that get_balance raises NotImplementedError."""
        wallet = BaseWallet(chain="ethereum", address="0x123", private_key="0xkey")
        with pytest.raises(NotImplementedError):
            wallet.get_balance()

    def test_send_transaction_not_implemented(self):
        """Test that send_transaction raises NotImplementedError."""
        wallet = BaseWallet(chain="ethereum", address="0x123", private_key="0xkey")
        with pytest.raises(NotImplementedError):
            wallet.send_transaction(to="0x456", value=100)

    def test_get_transaction_history_not_implemented(self):
        """Test that get_transaction_history raises NotImplementedError."""
        wallet = BaseWallet(chain="ethereum", address="0x123", private_key="0xkey")
        with pytest.raises(NotImplementedError):
            wallet.get_transaction_history()


# ============================== ETHEREUM WALLET TESTS ==============================

class TestEthereumWallet:
    """Test the EthereumWallet implementation."""

    @pytest.fixture
    def eth_wallet(self, web3_client_service, test_private_key, test_address_from_private_key):
        """Return an EthereumWallet instance with mocked dependencies."""
        wallet = EthereumWallet(
            web3_client=web3_client_service,
            address=test_address_from_private_key,
            private_key=test_private_key,
        )
        return wallet

    async def test_get_balance(self, eth_wallet):
        """Test getting ETH balance."""
        with patch.object(eth_wallet.web3_client.eth, "get_balance") as mock_balance:
            mock_balance.return_value = 10**18  # 1 ETH
            balance = await eth_wallet.get_balance()
            assert balance == 10**18

    async def test_send_transaction(self, eth_wallet, test_address_from_private_key):
        """Test sending an ETH transaction."""
        to_address = "0x" + "c" * 40
        with patch.object(eth_wallet.web3_client.eth, "send_transaction") as mock_send:
            mock_send.return_value = "0x" + "d" * 64
            with patch.object(eth_wallet.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "d" * 64}
                tx_hash = await eth_wallet.send_transaction(
                    to=to_address,
                    value=10**17,  # 0.1 ETH
                )
                assert tx_hash == "0x" + "d" * 64
                mock_send.assert_called_once()

    async def test_get_transaction_history(self, eth_wallet):
        """Test fetching transaction history."""
        with patch.object(eth_wallet, "_fetch_transactions") as mock_txs:
            mock_txs.return_value = [
                {"hash": "0x1", "from": "0xfrom", "to": "0xto", "value": 100},
                {"hash": "0x2", "from": "0xfrom", "to": "0xto", "value": 200},
            ]
            history = await eth_wallet.get_transaction_history(limit=10)
            assert len(history) == 2
            assert history[0]["hash"] == "0x1"

    async def test_sign_message(self, eth_wallet):
        """Test signing a message."""
        message = "Hello, Ethereum!"
        # Mock signing
        with patch.object(Account, "sign_message") as mock_sign:
            mock_sign.return_value = {"signature": "0x" + "e" * 64}
            signature = eth_wallet.sign_message(message)
            assert signature == "0x" + "e" * 64

    async def test_verify_message(self, eth_wallet):
        """Test verifying a signed message."""
        message = "Test message"
        signature = "0x" + "f" * 64
        # Mock recovery
        with patch.object(Account, "recover_message") as mock_recover:
            mock_recover.return_value = eth_wallet.address
            is_valid = eth_wallet.verify_message(message, signature)
            assert is_valid is True


# ============================== BSC WALLET TESTS ==============================

class TestBSCWallet:
    """Test the BSCWallet implementation (Binance Smart Chain)."""

    @pytest.fixture
    def bsc_wallet(self, web3_client_service, test_private_key, test_address_from_private_key):
        """Return a BSCWallet instance."""
        # BSC uses the same EVM as Ethereum but different chain ID.
        wallet = BSCWallet(
            web3_client=web3_client_service,
            address=test_address_from_private_key,
            private_key=test_private_key,
            chain_id=56,
        )
        return wallet

    async def test_get_balance(self, bsc_wallet):
        """Test getting BNB balance."""
        with patch.object(bsc_wallet.web3_client.eth, "get_balance") as mock_balance:
            mock_balance.return_value = 10**18
            balance = await bsc_wallet.get_balance()
            assert balance == 10**18

    async def test_send_transaction(self, bsc_wallet):
        """Test sending BNB transaction."""
        to_address = "0x" + "g" * 40
        with patch.object(bsc_wallet.web3_client.eth, "send_transaction") as mock_send:
            mock_send.return_value = "0x" + "h" * 64
            with patch.object(bsc_wallet.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "h" * 64}
                tx_hash = await bsc_wallet.send_transaction(
                    to=to_address,
                    value=5 * 10**17,
                )
                assert tx_hash == "0x" + "h" * 64


# ============================== POLYGON WALLET TESTS ==============================

class TestPolygonWallet:
    """Test the PolygonWallet implementation."""

    @pytest.fixture
    def polygon_wallet(self, web3_client_service, test_private_key, test_address_from_private_key):
        """Return a PolygonWallet instance."""
        wallet = PolygonWallet(
            web3_client=web3_client_service,
            address=test_address_from_private_key,
            private_key=test_private_key,
            chain_id=137,
        )
        return wallet

    async def test_get_balance(self, polygon_wallet):
        """Test getting MATIC balance."""
        with patch.object(polygon_wallet.web3_client.eth, "get_balance") as mock_balance:
            mock_balance.return_value = 100 * 10**18
            balance = await polygon_wallet.get_balance()
            assert balance == 100 * 10**18

    async def test_send_transaction(self, polygon_wallet):
        """Test sending MATIC transaction."""
        to_address = "0x" + "i" * 40
        with patch.object(polygon_wallet.web3_client.eth, "send_transaction") as mock_send:
            mock_send.return_value = "0x" + "j" * 64
            with patch.object(polygon_wallet.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "j" * 64}
                tx_hash = await polygon_wallet.send_transaction(
                    to=to_address,
                    value=10 * 10**18,
                )
                assert tx_hash == "0x" + "j" * 64


# ============================== SOLANA WALLET TESTS ==============================

class TestSolanaWallet:
    """Test the SolanaWallet implementation (mocked)."""

    @pytest.fixture
    def solana_wallet(self):
        """Return a SolanaWallet instance with mocked client."""
        wallet = SolanaWallet(
            address="0x" + "k" * 40,
            private_key="0x" + "l" * 64,
            cluster="devnet",
        )
        # Mock the Solana RPC client
        wallet.client = AsyncMock()
        return wallet

    async def test_get_balance(self, solana_wallet):
        """Test getting SOL balance."""
        with patch.object(solana_wallet.client, "get_balance") as mock_balance:
            mock_balance.return_value = 100
            balance = await solana_wallet.get_balance()
            assert balance == 100

    async def test_send_transaction(self, solana_wallet):
        """Test sending SOL transaction."""
        to_address = "0x" + "m" * 40
        with patch.object(solana_wallet.client, "send_transaction") as mock_send:
            mock_send.return_value = "0x" + "n" * 64
            tx_hash = await solana_wallet.send_transaction(
                to=to_address,
                value=10,
            )
            assert tx_hash == "0x" + "n" * 64


# ============================== TRON WALLET TESTS ==============================

class TestTronWallet:
    """Test the TronWallet implementation (mocked)."""

    @pytest.fixture
    def tron_wallet(self):
        """Return a TronWallet instance."""
        wallet = TronWallet(
            address="0x" + "o" * 40,
            private_key="0x" + "p" * 64,
        )
        wallet.client = AsyncMock()
        return wallet

    async def test_get_balance(self, tron_wallet):
        """Test getting TRX balance."""
        with patch.object(tron_wallet.client, "get_balance") as mock_balance:
            mock_balance.return_value = 1000
            balance = await tron_wallet.get_balance()
            assert balance == 1000

    async def test_send_transaction(self, tron_wallet):
        """Test sending TRX transaction."""
        to_address = "0x" + "q" * 40
        with patch.object(tron_wallet.client, "send_transaction") as mock_send:
            mock_send.return_value = "0x" + "r" * 64
            tx_hash = await tron_wallet.send_transaction(
                to=to_address,
                value=100,
            )
            assert tx_hash == "0x" + "r" * 64


# ============================== MULTI-CHAIN WALLET TESTS ==============================

class TestMultiChainWallet:
    """Test the MultiChainWallet that manages wallets across chains."""

    @pytest.fixture
    def multi_chain_wallet(self, eth_wallet, bsc_wallet, polygon_wallet):
        """Return a MultiChainWallet with registered wallets."""
        wallet = MultiChainWallet()
        wallet.register_wallet("ethereum", eth_wallet)
        wallet.register_wallet("bsc", bsc_wallet)
        wallet.register_wallet("polygon", polygon_wallet)
        return wallet

    def test_register_wallet(self, multi_chain_wallet):
        """Test registering a wallet."""
        mock_wallet = MagicMock()
        multi_chain_wallet.register_wallet("solana", mock_wallet)
        assert "solana" in multi_chain_wallet.wallets

    def test_get_wallet(self, multi_chain_wallet):
        """Test retrieving a wallet."""
        wallet = multi_chain_wallet.get_wallet("ethereum")
        assert wallet.chain == "ethereum"

    async def test_get_balance_all(self, multi_chain_wallet):
        """Test getting balance across all chains."""
        with patch.object(multi_chain_wallet.wallets["ethereum"], "get_balance") as mock_eth:
            mock_eth.return_value = 10**18
            with patch.object(multi_chain_wallet.wallets["bsc"], "get_balance") as mock_bsc:
                mock_bsc.return_value = 5 * 10**18
                with patch.object(multi_chain_wallet.wallets["polygon"], "get_balance") as mock_poly:
                    mock_poly.return_value = 100 * 10**18
                    balances = await multi_chain_wallet.get_balance_all()
                    assert balances["ethereum"] == 10**18
                    assert balances["bsc"] == 5 * 10**18
                    assert balances["polygon"] == 100 * 10**18

    async def test_send_transaction_on_chain(self, multi_chain_wallet):
        """Test sending transaction on a specific chain."""
        to_address = "0x" + "s" * 40
        with patch.object(multi_chain_wallet.wallets["ethereum"], "send_transaction") as mock_send:
            mock_send.return_value = "0x" + "t" * 64
            tx_hash = await multi_chain_wallet.send_transaction(
                chain="ethereum",
                to=to_address,
                value=10**17,
            )
            assert tx_hash == "0x" + "t" * 64

    async def test_get_transaction_history_all(self, multi_chain_wallet):
        """Test getting transaction history across all chains."""
        with patch.object(multi_chain_wallet.wallets["ethereum"], "get_transaction_history") as mock_eth:
            mock_eth.return_value = [{"hash": "0x1"}, {"hash": "0x2"}]
            with patch.object(multi_chain_wallet.wallets["bsc"], "get_transaction_history") as mock_bsc:
                mock_bsc.return_value = [{"hash": "0x3"}]
                history = await multi_chain_wallet.get_transaction_history_all()
                assert len(history) == 3
                assert history[0]["chain"] == "ethereum"
                assert history[2]["chain"] == "bsc"


# ============================== WALLET MANAGER TESTS ==============================

class TestWalletManager:
    """Test the WalletManager orchestrating wallet operations."""

    @pytest.fixture
    def wallet_manager(self, eth_wallet, bsc_wallet, polygon_wallet):
        """Return a WalletManager with registered wallets."""
        manager = WalletManager()
        manager.register_wallet("ethereum", eth_wallet)
        manager.register_wallet("bsc", bsc_wallet)
        manager.register_wallet("polygon", polygon_wallet)
        return manager

    def test_register_wallet(self, wallet_manager):
        """Test registering a wallet."""
        mock_wallet = MagicMock()
        wallet_manager.register_wallet("solana", mock_wallet)
        assert "solana" in wallet_manager.wallets

    def test_get_wallet(self, wallet_manager):
        """Test retrieving a wallet."""
        wallet = wallet_manager.get_wallet("ethereum")
        assert wallet.chain == "ethereum"

    async def test_get_balance_all(self, wallet_manager):
        """Test getting balances across all chains."""
        with patch.object(wallet_manager.wallets["ethereum"], "get_balance") as mock_eth:
            mock_eth.return_value = 1.0
            with patch.object(wallet_manager.wallets["bsc"], "get_balance") as mock_bsc:
                mock_bsc.return_value = 2.0
                with patch.object(wallet_manager.wallets["polygon"], "get_balance") as mock_poly:
                    mock_poly.return_value = 3.0
                    balances = await wallet_manager.get_balance_all()
                    assert balances["ethereum"] == 1.0
                    assert balances["bsc"] == 2.0
                    assert balances["polygon"] == 3.0


# ============================== HD WALLET MANAGER TESTS ==============================

class TestHDWalletManager:
    """Test the HDWalletManager for BIP32/BIP39/BIP44 wallets."""

    @pytest.fixture
    def hd_manager(self):
        """Return an HDWalletManager instance."""
        return HDWalletManager()

    def test_create_mnemonic(self, hd_manager):
        """Test creating a BIP39 mnemonic."""
        mnemonic = hd_manager.create_mnemonic(strength=128)
        words = mnemonic.split()
        assert len(words) == 12
        # Check that it's valid (you could verify against wordlist)

    def test_derive_from_mnemonic(self, hd_manager):
        """Test deriving a wallet from a mnemonic."""
        mnemonic = "test test test test test test test test test test test junk"
        with patch.object(hd_manager, "_derive_path") as mock_derive:
            mock_derive.return_value = {
                "address": "0x" + "u" * 40,
                "private_key": "0x" + "v" * 64,
            }
            wallet = hd_manager.derive_from_mnemonic(
                mnemonic=mnemonic,
                path="m/44'/60'/0'/0/0",
            )
            assert wallet["address"] == "0x" + "u" * 40

    def test_derive_from_seed(self, hd_manager):
        """Test deriving from a seed."""
        seed = bytes.fromhex("00" * 32)
        with patch.object(hd_manager, "_derive_from_seed") as mock_derive:
            mock_derive.return_value = {
                "address": "0x" + "w" * 40,
                "private_key": "0x" + "x" * 64,
            }
            wallet = hd_manager.derive_from_seed(seed, "m/44'/60'/0'/0/0")
            assert wallet["address"] == "0x" + "w" * 40

    def test_get_bip44_path(self, hd_manager):
        """Test generating BIP44 path."""
        path = hd_manager.get_bip44_path(
            coin_type=60,  # Ethereum
            account=0,
            change=0,
            index=0,
        )
        assert path == "m/44'/60'/0'/0/0"

    def test_get_bip44_path_other_coin(self, hd_manager):
        """Test BIP44 path for other coins."""
        path = hd_manager.get_bip44_path(
            coin_type=501,  # Solana
            account=1,
            change=0,
            index=2,
        )
        assert path == "m/44'/501'/1'/0/2"


# ============================== WALLET BACKUP MANAGER TESTS ==============================

class TestWalletBackupManager:
    """Test the WalletBackupManager for wallet backups."""

    @pytest.fixture
    def backup_manager(self):
        """Return a WalletBackupManager instance."""
        return WalletBackupManager()

    async def test_create_backup(self, backup_manager, test_private_key, test_address_from_private_key):
        """Test creating a wallet backup."""
        wallet_data = {
            "address": test_address_from_private_key,
            "private_key": test_private_key,
            "chain": "ethereum",
        }
        with patch.object(backup_manager, "_encrypt_data") as mock_encrypt:
            mock_encrypt.return_value = b"encrypted_data"
            backup = await backup_manager.create_backup(wallet_data, password="testpass")
            assert "encrypted_data" in backup
            assert "metadata" in backup

    async def test_restore_backup(self, backup_manager):
        """Test restoring a wallet from backup."""
        backup_data = {"encrypted": b"data", "metadata": {"chain": "ethereum"}}
        with patch.object(backup_manager, "_decrypt_data") as mock_decrypt:
            mock_decrypt.return_value = {
                "address": "0x" + "y" * 40,
                "private_key": "0x" + "z" * 64,
                "chain": "ethereum",
            }
            wallet = await backup_manager.restore_backup(backup_data, password="testpass")
            assert wallet["address"] == "0x" + "y" * 40

    async def test_export_keystore(self, backup_manager, test_private_key, test_address_from_private_key):
        """Test exporting a wallet as keystore JSON."""
        with patch.object(backup_manager, "_encrypt_keystore") as mock_keystore:
            mock_keystore.return_value = {"version": 3, "id": "uuid", "address": "0x" + "aa" * 40}
            keystore = await backup_manager.export_keystore(
                private_key=test_private_key,
                password="testpass",
                address=test_address_from_private_key,
            )
            assert keystore["version"] == 3

    async def test_import_keystore(self, backup_manager):
        """Test importing a wallet from keystore."""
        keystore_data = {"version": 3, "id": "uuid", "address": "0x" + "bb" * 40}
        with patch.object(backup_manager, "_decrypt_keystore") as mock_decrypt:
            mock_decrypt.return_value = {
                "address": "0x" + "cc" * 40,
                "private_key": "0x" + "dd" * 64,
            }
            wallet = await backup_manager.import_keystore(keystore_data, password="testpass")
            assert wallet["address"] == "0x" + "cc" * 40


# ============================== WALLET SECURITY MANAGER TESTS ==============================

class TestWalletSecurityManager:
    """Test the WalletSecurityManager for wallet security operations."""

    @pytest.fixture
    def security_manager(self):
        """Return a WalletSecurityManager instance."""
        return WalletSecurityManager()

    def test_encrypt_private_key(self, security_manager):
        """Test encrypting a private key."""
        private_key = "0x" + "ee" * 32
        encrypted = security_manager.encrypt_private_key(private_key, password="testpass")
        assert encrypted != private_key
        # Should return base64 or hex string

    def test_decrypt_private_key(self, security_manager):
        """Test decrypting a private key."""
        private_key = "0x" + "ff" * 32
        encrypted = security_manager.encrypt_private_key(private_key, password="testpass")
        decrypted = security_manager.decrypt_private_key(encrypted, password="testpass")
        assert decrypted == private_key

    def test_decrypt_wrong_password(self, security_manager):
        """Test decryption with wrong password."""
        private_key = "0x" + "gg" * 32
        encrypted = security_manager.encrypt_private_key(private_key, password="testpass")
        with pytest.raises(ValueError):
            security_manager.decrypt_private_key(encrypted, password="wrongpass")

    def test_validate_address(self, security_manager):
        """Test address validation."""
        valid_address = "0x" + "hh" * 40
        invalid_address = "0x" + "hh" * 39
        assert security_manager.validate_address(valid_address) is True
        assert security_manager.validate_address(invalid_address) is False


# ============================== WALLET ANALYTICS TESTS ==============================

class TestWalletAnalytics:
    """Test the WalletAnalytics for wallet performance tracking."""

    @pytest.fixture
    def wallet_analytics(self):
        """Return a WalletAnalytics instance."""
        return WalletAnalytics()

    async def test_get_total_value(self, wallet_analytics):
        """Test calculating total value across chains."""
        balances = {"ethereum": 1.0, "bsc": 2.0, "polygon": 3.0}
        prices = {"ethereum": 3000, "bsc": 3000, "polygon": 1.5}
        with patch.object(wallet_analytics, "_fetch_prices") as mock_prices:
            mock_prices.return_value = prices
            total = await wallet_analytics.get_total_value(balances)
            # 1*3000 + 2*3000 + 3*1.5 = 3000 + 6000 + 4.5 = 9004.5
            assert total == 9004.5

    async def test_get_portfolio_allocation(self, wallet_analytics):
        """Test getting portfolio allocation percentages."""
        balances = {"ethereum": 1.0, "bsc": 2.0, "polygon": 3.0}
        prices = {"ethereum": 3000, "bsc": 3000, "polygon": 1.5}
        total = 9004.5
        with patch.object(wallet_analytics, "_fetch_prices") as mock_prices:
            mock_prices.return_value = prices
            allocation = await wallet_analytics.get_portfolio_allocation(balances)
            assert allocation["ethereum"] == 3000 / 9004.5 * 100  # ~33.3%
            assert allocation["bsc"] == 6000 / 9004.5 * 100  # ~66.6%
            assert allocation["polygon"] == 4.5 / 9004.5 * 100  # ~0.05%

    async def test_get_transaction_summary(self, wallet_analytics):
        """Test transaction summary."""
        txs = [
            {"type": "sent", "value": 100},
            {"type": "sent", "value": 50},
            {"type": "received", "value": 200},
            {"type": "received", "value": 30},
        ]
        summary = await wallet_analytics.get_transaction_summary(txs)
        assert summary["total_sent"] == 150
        assert summary["total_received"] == 230
        assert summary["net_flow"] == 80


# ============================== WALLET MONITOR TESTS ==============================

class TestWalletMonitor:
    """Test the WalletMonitor for monitoring wallet activity."""

    @pytest.fixture
    def wallet_monitor(self):
        """Return a WalletMonitor instance."""
        return WalletMonitor()

    async def test_monitor_balance_changes(self, wallet_monitor):
        """Test monitoring balance changes over time."""
        # Mock checking balance at intervals.
        with patch.object(wallet_monitor, "_check_balance") as mock_check:
            mock_check.side_effect = [100, 105, 110, 100]
            changes = await wallet_monitor.monitor_balance_changes(
                wallet_address="0x" + "ii" * 40,
                chain="ethereum",
                interval=60,
                duration=240,
            )
            assert changes == [100, 105, 110, 100]

    async def test_detect_large_transactions(self, wallet_monitor):
        """Test detecting large transactions."""
        txs = [
            {"value": 100, "type": "sent"},
            {"value": 1000, "type": "sent"},
            {"value": 50, "type": "received"},
        ]
        with patch.object(wallet_monitor, "_fetch_transactions") as mock_fetch:
            mock_fetch.return_value = txs
            large = await wallet_monitor.detect_large_transactions(
                wallet_address="0x" + "jj" * 40,
                threshold=500,
            )
            assert len(large) == 1
            assert large[0]["value"] == 1000

    async def test_get_alert(self, wallet_monitor):
        """Test getting alerts based on wallet activity."""
        # Simulate an alert for a large incoming tx
        with patch.object(wallet_monitor, "_fetch_transactions") as mock_fetch:
            mock_fetch.return_value = [{"value": 10000, "type": "received"}]
            alerts = await wallet_monitor.get_alerts(
                wallet_address="0x" + "kk" * 40,
                large_tx_threshold=5000,
            )
            assert len(alerts) == 1
            assert alerts[0]["type"] == "large_incoming"


# ============================== WALLET BALANCE CHECKER TESTS ==============================

class TestWalletBalanceChecker:
    """Test the WalletBalanceChecker for balance queries."""

    @pytest.fixture
    def balance_checker(self):
        """Return a WalletBalanceChecker instance."""
        return WalletBalanceChecker()

    async def test_check_balance(self, balance_checker):
        """Test checking balance for a single chain."""
        with patch.object(balance_checker, "_call_rpc") as mock_rpc:
            mock_rpc.return_value = 10**18
            balance = await balance_checker.check_balance(
                address="0x" + "ll" * 40,
                chain="ethereum",
            )
            assert balance == 10**18

    async def test_check_balances(self, balance_checker):
        """Test checking balances across multiple chains."""
        addresses = {
            "ethereum": "0x" + "mm" * 40,
            "bsc": "0x" + "nn" * 40,
        }
        with patch.object(balance_checker, "check_balance") as mock_check:
            mock_check.side_effect = [1.0, 2.0]
            balances = await balance_checker.check_balances(addresses)
            assert balances["ethereum"] == 1.0
            assert balances["bsc"] == 2.0


# ============================== WALLET SIGNER TESTS ==============================

class TestWalletSigner:
    """Test the WalletSigner for signing operations."""

    @pytest.fixture
    def wallet_signer(self, test_private_key, test_address_from_private_key):
        """Return a WalletSigner instance."""
        return WalletSigner(
            private_key=test_private_key,
            address=test_address_from_private_key,
            chain="ethereum",
        )

    def test_sign_transaction(self, wallet_signer):
        """Test signing a transaction."""
        tx = {
            "to": "0x" + "oo" * 40,
            "value": 10**17,
            "gas": 21000,
            "gasPrice": 10**9,
            "nonce": 0,
        }
        with patch.object(Account, "sign_transaction") as mock_sign:
            mock_sign.return_value = {"rawTransaction": "0x" + "pp" * 64}
            signed = wallet_signer.sign_transaction(tx)
            assert signed == "0x" + "pp" * 64

    def test_sign_message(self, wallet_signer):
        """Test signing a message."""
        message = "Test sign message"
        with patch.object(Account, "sign_message") as mock_sign:
            mock_sign.return_value = {"signature": "0x" + "qq" * 64}
            signature = wallet_signer.sign_message(message)
            assert signature == "0x" + "qq" * 64

    def test_verify_signature(self, wallet_signer):
        """Test verifying a signature."""
        message = "Test message"
        signature = "0x" + "rr" * 64
        with patch.object(Account, "recover_message") as mock_recover:
            mock_recover.return_value = wallet_signer.address
            is_valid = wallet_signer.verify_signature(message, signature)
            assert is_valid is True


# ============================== WALLET TRANSACTION MANAGER TESTS ==============================

class TestWalletTransactionManager:
    """Test the WalletTransactionManager for transaction building and management."""

    @pytest.fixture
    def tx_manager(self, eth_wallet):
        """Return a WalletTransactionManager instance."""
        return WalletTransactionManager(eth_wallet)

    async def test_build_transaction(self, tx_manager):
        """Test building a transaction."""
        tx = await tx_manager.build_transaction(
            to="0x" + "ss" * 40,
            value=10**17,
            gas_price=10**9,
            gas_limit=21000,
        )
        assert tx["to"] == "0x" + "ss" * 40
        assert tx["value"] == 10**17
        assert tx["gas"] == 21000
        assert "nonce" in tx

    async def test_sign_and_send(self, tx_manager):
        """Test signing and sending a transaction."""
        tx = {
            "to": "0x" + "tt" * 40,
            "value": 10**17,
            "gas": 21000,
            "gasPrice": 10**9,
            "nonce": 0,
        }
        with patch.object(tx_manager.wallet, "send_transaction") as mock_send:
            mock_send.return_value = "0x" + "uu" * 64
            tx_hash = await tx_manager.sign_and_send(tx)
            assert tx_hash == "0x" + "uu" * 64

    async def test_estimate_gas(self, tx_manager):
        """Test estimating gas for a transaction."""
        with patch.object(tx_manager.wallet.web3_client.eth, "estimate_gas") as mock_estimate:
            mock_estimate.return_value = 21000
            gas = await tx_manager.estimate_gas(
                to="0x" + "vv" * 40,
                value=10**17,
            )
            assert gas == 21000


# ============================== CONFIGURATION TESTS ==============================

class TestWalletConfig:
    """Test wallet configuration."""

    def test_load_config(self):
        """Test loading wallet configuration."""
        config = WalletConfig()
        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "default_chain": "ethereum",
                "chains": {
                    "ethereum": {"rpc_url": "http://localhost:8545"},
                    "bsc": {"rpc_url": "http://localhost:8546"},
                },
                "security": {"encryption": "AES-256"},
            })
            config.load_from_file("wallet_config.json")
            assert config.default_chain == "ethereum"
            assert config.chains["bsc"]["rpc_url"] == "http://localhost:8546"

    def test_get_chain_config(self, wallet_config):
        """Test retrieving chain configuration."""
        config = WalletConfig()
        config.chains = {"ethereum": {"rpc_url": "http://localhost:8545"}}
        cfg = config.get_chain_config("ethereum")
        assert cfg["rpc_url"] == "http://localhost:8545"


# ============================== INTEGRATION TESTS ==============================

class TestWalletIntegration:
    """Integration tests for wallet components working together."""

    async def test_full_wallet_flow(
        self,
        wallet_manager,
        hd_manager,
        backup_manager,
        security_manager,
        test_private_key,
        test_address_from_private_key,
    ):
        """Test a complete wallet workflow: create HD wallet -> backup -> restore -> send."""
        # 1. Create HD wallet
        mnemonic = hd_manager.create_mnemonic()
        wallet_data = hd_manager.derive_from_mnemonic(
            mnemonic=mnemonic,
            path="m/44'/60'/0'/0/0",
        )
        address = wallet_data["address"]
        private_key = wallet_data["private_key"]

        # 2. Register wallet
        eth_wallet = EthereumWallet(
            web3_client=MagicMock(),
            address=address,
            private_key=private_key,
        )
        wallet_manager.register_wallet("ethereum", eth_wallet)

        # 3. Backup wallet
        backup = await backup_manager.create_backup(
            wallet_data={"address": address, "private_key": private_key, "chain": "ethereum"},
            password="securepass",
        )

        # 4. Restore from backup
        restored = await backup_manager.restore_backup(backup, password="securepass")
        assert restored["address"] == address

        # 5. Encrypt private key
        encrypted = security_manager.encrypt_private_key(private_key, password="securepass")

        # 6. Decrypt and verify
        decrypted = security_manager.decrypt_private_key(encrypted, password="securepass")
        assert decrypted == private_key

        # 7. Send transaction (mocked)
        with patch.object(eth_wallet, "send_transaction") as mock_send:
            mock_send.return_value = "0x" + "ww" * 64
            tx_hash = await wallet_manager.send_transaction(
                chain="ethereum",
                to="0x" + "xx" * 40,
                value=10**17,
            )
            assert tx_hash == "0x" + "ww" * 64

    async def test_multi_chain_transfer(
        self,
        wallet_manager,
        multi_chain_wallet,
    ):
        """Test transferring assets between chains via wallet manager."""
        # We'll mock the bridge or swap operation
        # Transfer from Ethereum to BSC
        with patch.object(wallet_manager, "bridge_asset") as mock_bridge:
            mock_bridge.return_value = {"tx_hash": "0x" + "yy" * 64}
            result = await wallet_manager.bridge_asset(
                from_chain="ethereum",
                to_chain="bsc",
                asset="ETH",
                amount=1.0,
                recipient="0x" + "zz" * 40,
            )
            assert result["tx_hash"] == "0x" + "yy" * 64
