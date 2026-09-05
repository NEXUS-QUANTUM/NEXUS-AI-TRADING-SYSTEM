"""
Web3 Wallet Module
====================

This module provides a comprehensive wallet implementation for Ethereum and
EVM-compatible blockchains. It supports key management, transaction signing,
balance checking, token transfers, and secure storage of private keys.

Features:
- Create new wallets (random private key)
- Import existing wallets (private key, mnemonic)
- Securely store and encrypt private keys (keystore)
- Send ETH and ERC20 tokens
- Check balances (ETH and tokens)
- Sign and verify messages
- Transaction history
- Multi-network support (Ethereum, Polygon, BSC, etc.)
- Integration with Web3 client and gas management
"""

import json
import os
import time
import logging
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys
from eth_utils import to_checksum_address, to_hex
from web3 import Web3
from web3.types import TxParams, Wei

from trading.bots.swing_bot.utils.cache import MemoryCache
from trading.bots.swing_bot.utils.converters import to_int, to_float, to_str
from trading.bots.swing_bot.utils.crypto_utils import encrypt_fernet, decrypt_fernet, generate_key
from trading.bots.swing_bot.utils.helpers import load_json, save_json
from trading.bots.swing_bot.utils.validators import validate_data

from .web3_client import Web3Client
from .web3_utils import Web3Utils, create_web3_utils
from .web3_gas import GasManager, create_gas_manager
from .web3_token import TokenManager, create_token_manager

logger = logging.getLogger(__name__)


@dataclass
class WalletInfo:
    """Wallet information."""
    address: str
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    mnemonic: Optional[str] = None
    path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    network: str = "ethereum"
    chain_id: int = 1
    is_encrypted: bool = False
    name: Optional[str] = None
    balance: Optional[float] = None
    balance_updated_at: Optional[datetime] = None


@dataclass
class TransactionInfo:
    """Transaction information."""
    hash: str
    from_address: str
    to_address: str
    value: float
    gas_used: int
    gas_price: int
    block_number: int
    timestamp: datetime
    status: str  # 'confirmed', 'pending', 'failed'
    data: Optional[str] = None
    token_symbol: Optional[str] = None
    token_address: Optional[str] = None
    token_decimals: Optional[int] = None


class Web3Wallet:
    """
    Web3 wallet implementation for managing accounts and transactions.
    
    Provides full wallet functionality including key management, signing,
    sending transactions, and token interactions.
    """
    
    def __init__(
        self,
        web3_client: Any,
        private_key: Optional[str] = None,
        mnemonic: Optional[str] = None,
        address: Optional[str] = None,
        password: Optional[str] = None,
        keystore_path: Optional[Union[str, Path]] = None,
        network: str = "ethereum",
        gas_manager: Optional[GasManager] = None,
        token_manager: Optional[TokenManager] = None,
        utils: Optional[Web3Utils] = None,
        enable_cache: bool = True,
        cache_ttl: int = 60,
    ):
        """
        Initialize the Web3 wallet.
        
        Args:
            web3_client: Web3 client instance.
            private_key: Private key (hex string) to import.
            mnemonic: Mnemonic phrase to import.
            address: Address (optional if private_key is provided).
            password: Password for decrypting keystore.
            keystore_path: Path to keystore file.
            network: Network name.
            gas_manager: Gas manager instance.
            token_manager: Token manager instance.
            utils: Web3 utilities instance.
            enable_cache: Enable caching.
            cache_ttl: Cache TTL in seconds.
        """
        self.web3_client = web3_client
        self.network = network
        self.chain_id = web3_client.chain_id
        self.password = password
        
        # Initialize utilities
        self.utils = utils or create_web3_utils(web3_client)
        self.gas_manager = gas_manager or create_gas_manager(web3_client)
        self.token_manager = token_manager or create_token_manager(web3_client)
        
        # Cache
        self._cache = MemoryCache(max_size=100, default_ttl=cache_ttl) if enable_cache else None
        
        # Initialize account
        self._account = None
        self._info: Optional[WalletInfo] = None
        
        # Set account based on provided credentials
        if keystore_path:
            self._load_keystore(keystore_path, password)
        elif private_key:
            self._import_private_key(private_key, address)
        elif mnemonic:
            self._import_mnemonic(mnemonic, address)
        else:
            # Create new wallet
            self._create_new_wallet()
        
        # Validate that we have an account
        if self._account is None:
            raise ValueError("Failed to initialize wallet account")
        
        # Update Web3 client with account
        self.web3_client.set_private_key(self._account.key.hex())
        
        # Initial balance fetch
        self._update_balance()
        
        logger.info(f"Wallet initialized: {self.address} on {network}")
    
    # ============ Creation / Import Methods ============
    
    def _create_new_wallet(self) -> None:
        """Create a new wallet with random private key."""
        self._account = Account.create()
        self._info = WalletInfo(
            address=self._account.address,
            private_key=self._account.key.hex(),
            public_key=self._account.key.public_key.to_hex(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            network=self.network,
            chain_id=self.chain_id
        )
        logger.info(f"Created new wallet: {self._account.address}")
    
    def _import_private_key(self, private_key: str, address: Optional[str] = None) -> None:
        """
        Import wallet from private key.
        
        Args:
            private_key: Private key (hex string).
            address: Optional address (will be derived from key if not provided).
        """
        try:
            self._account = Account.from_key(private_key)
            if address and self._account.address.lower() != address.lower():
                raise ValueError(f"Address mismatch: provided {address}, derived {self._account.address}")
            
            self._info = WalletInfo(
                address=self._account.address,
                private_key=private_key,
                public_key=self._account.key.public_key.to_hex(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                network=self.network,
                chain_id=self.chain_id
            )
            logger.info(f"Imported wallet from private key: {self._account.address}")
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}")
    
    def _import_mnemonic(self, mnemonic: str, address: Optional[str] = None) -> None:
        """
        Import wallet from mnemonic phrase.
        
        Args:
            mnemonic: Mnemonic phrase (12 or 24 words).
            address: Optional address (derived from first account if not provided).
        """
        try:
            # Derive private key from mnemonic
            Account.enable_unaudited_hdwallet_features()
            self._account = Account.from_mnemonic(mnemonic)
            
            if address and self._account.address.lower() != address.lower():
                raise ValueError(f"Address mismatch: provided {address}, derived {self._account.address}")
            
            self._info = WalletInfo(
                address=self._account.address,
                private_key=self._account.key.hex(),
                public_key=self._account.key.public_key.to_hex(),
                mnemonic=mnemonic,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                network=self.network,
                chain_id=self.chain_id
            )
            logger.info(f"Imported wallet from mnemonic: {self._account.address}")
        except Exception as e:
            raise ValueError(f"Invalid mnemonic: {e}")
    
    def _load_keystore(self, keystore_path: Union[str, Path], password: Optional[str] = None) -> None:
        """
        Load wallet from encrypted keystore file.
        
        Args:
            keystore_path: Path to keystore file.
            password: Password to decrypt keystore.
        """
        keystore_path = Path(keystore_path)
        if not keystore_path.exists():
            raise FileNotFoundError(f"Keystore file not found: {keystore_path}")
        
        try:
            with open(keystore_path, 'r') as f:
                keystore_data = json.load(f)
            
            if password is None:
                raise ValueError("Password required to decrypt keystore")
            
            self._account = Account.decrypt(keystore_data, password)
            
            self._info = WalletInfo(
                address=self._account.address,
                private_key=self._account.key.hex(),
                public_key=self._account.key.public_key.to_hex(),
                created_at=datetime.fromtimestamp(keystore_data.get('created_at', time.time())),
                updated_at=datetime.now(),
                network=self.network,
                chain_id=self.chain_id,
                is_encrypted=True
            )
            self.password = password
            logger.info(f"Loaded keystore wallet: {self._account.address}")
        except Exception as e:
            raise ValueError(f"Failed to load keystore: {e}")
    
    # ============ Properties ============
    
    @property
    def address(self) -> str:
        """Get the wallet address."""
        return self._account.address
    
    @property
    def private_key(self) -> Optional[str]:
        """Get the private key (if available)."""
        return self._info.private_key if self._info else None
    
    @property
    def public_key(self) -> Optional[str]:
        """Get the public key."""
        return self._info.public_key if self._info else None
    
    @property
    def info(self) -> WalletInfo:
        """Get wallet information."""
        return self._info
    
    @property
    def balance(self) -> Optional[float]:
        """Get cached balance."""
        return self._info.balance if self._info else None
    
    # ============ Balance Methods ============
    
    def _update_balance(self) -> float:
        """Update and return current ETH balance."""
        try:
            balance = self.web3_client.get_balance(self.address)
            if self._info:
                self._info.balance = balance
                self._info.balance_updated_at = datetime.now()
            return balance
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0
    
    def get_balance(self, refresh: bool = False) -> float:
        """
        Get the current ETH balance.
        
        Args:
            refresh: Force refresh from blockchain.
            
        Returns:
            Balance in ETH.
        """
        if not refresh and self._info and self._info.balance is not None:
            # Use cached balance if not expired (5 minutes)
            if self._info.balance_updated_at:
                age = (datetime.now() - self._info.balance_updated_at).total_seconds()
                if age < 300:
                    return self._info.balance
        
        return self._update_balance()
    
    def get_token_balance(self, token_address: str, decimals: Optional[int] = None) -> float:
        """
        Get token balance for this wallet.
        
        Args:
            token_address: Token contract address.
            decimals: Token decimals (auto-fetched if None).
            
        Returns:
            Token balance in token units.
        """
        return self.token_manager.get_token_balance(token_address, self.address, 'erc20', decimals)
    
    def get_all_token_balances(self, token_addresses: List[str]) -> Dict[str, float]:
        """
        Get balances for multiple tokens.
        
        Args:
            token_addresses: List of token addresses.
            
        Returns:
            Dictionary of token_address -> balance.
        """
        return self.token_manager.get_token_balances_batch(token_addresses, self.address)
    
    # ============ Transaction Methods ============
    
    def send_transaction(
        self,
        to: str,
        amount: Union[float, int, str],
        data: Optional[str] = None,
        gas_limit: Optional[int] = None,
        gas_price: Optional[int] = None,
        max_fee_per_gas: Optional[int] = None,
        max_priority_fee_per_gas: Optional[int] = None,
        gas_strategy: str = "standard",
        wait_for_confirmation: bool = True,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Send ETH to an address.
        
        Args:
            to: Recipient address.
            amount: Amount in ETH.
            data: Optional transaction data.
            gas_limit: Gas limit.
            gas_price: Gas price in wei.
            max_fee_per_gas: Max fee per gas (EIP-1559).
            max_priority_fee_per_gas: Max priority fee (EIP-1559).
            gas_strategy: Gas strategy.
            wait_for_confirmation: Wait for transaction confirmation.
            timeout: Timeout in seconds.
            
        Returns:
            Transaction receipt or hash.
        """
        to = to_checksum_address(to)
        
        # Build transaction
        tx = self.web3_client.build_transaction(
            to=to,
            value=amount,
            data=data,
            from_address=self.address,
            gas=gas_limit,
            gas_price=gas_price,
            max_fee_per_gas=max_fee_per_gas,
            max_priority_fee_per_gas=max_priority_fee_per_gas,
            gas_strategy=gas_strategy
        )
        
        # Sign and send
        signed_tx = self._account.sign_transaction(tx)
        tx_hash = self.web3_client.send_raw_transaction(signed_tx.raw_transaction)
        
        result = {
            'hash': tx_hash.hex(),
            'from': self.address,
            'to': to,
            'value': amount,
            'nonce': tx['nonce']
        }
        
        if wait_for_confirmation:
            receipt = self.web3_client.wait_for_transaction_receipt(tx_hash.hex(), timeout)
            result['receipt'] = receipt
            
            # Update balance
            self._update_balance()
        
        logger.info(f"Transaction sent: {result['hash']}")
        return result
    
    def send_erc20(
        self,
        token_address: str,
        to: str,
        amount: Union[float, int, str],
        decimals: Optional[int] = None,
        gas_limit: Optional[int] = None,
        gas_price: Optional[int] = None,
        max_fee_per_gas: Optional[int] = None,
        max_priority_fee_per_gas: Optional[int] = None,
        gas_strategy: str = "standard",
        wait_for_confirmation: bool = True,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Send ERC20 tokens.
        
        Args:
            token_address: Token contract address.
            to: Recipient address.
            amount: Amount in token units.
            decimals: Token decimals (auto-fetched if None).
            gas_limit: Gas limit.
            gas_price: Gas price in wei.
            max_fee_per_gas: Max fee per gas (EIP-1559).
            max_priority_fee_per_gas: Max priority fee.
            gas_strategy: Gas strategy.
            wait_for_confirmation: Wait for confirmation.
            timeout: Timeout in seconds.
            
        Returns:
            Transaction receipt or hash.
        """
        token_address = to_checksum_address(token_address)
        to = to_checksum_address(to)
        
        # Get token info
        info = self.token_manager.get_token_info(token_address)
        decimals = decimals or info.decimals
        
        # Convert amount to wei
        amount_wei = int(Decimal(str(amount)) * (10 ** decimals))
        
        # Encode transfer function
        data = self.token_manager.multicall._encode_function_call(
            token_address, 'transfer', to, amount_wei
        )
        
        # Build transaction
        tx = self.web3_client.build_transaction(
            to=token_address,
            value=0,
            data=data,
            from_address=self.address,
            gas=gas_limit,
            gas_price=gas_price,
            max_fee_per_gas=max_fee_per_gas,
            max_priority_fee_per_gas=max_priority_fee_per_gas,
            gas_strategy=gas_strategy
        )
        
        # Sign and send
        signed_tx = self._account.sign_transaction(tx)
        tx_hash = self.web3_client.send_raw_transaction(signed_tx.raw_transaction)
        
        result = {
            'hash': tx_hash.hex(),
            'from': self.address,
            'to': to,
            'token_address': token_address,
            'amount': amount,
            'symbol': info.symbol,
            'nonce': tx['nonce']
        }
        
        if wait_for_confirmation:
            receipt = self.web3_client.wait_for_transaction_receipt(tx_hash.hex(), timeout)
            result['receipt'] = receipt
        
        logger.info(f"ERC20 transfer sent: {result['hash']}")
        return result
    
    # ============ Message Signing ============
    
    def sign_message(self, message: str) -> str:
        """
        Sign a message with the wallet's private key.
        
        Args:
            message: Message to sign.
            
        Returns:
            Signature as hex string.
        """
        message_hash = encode_defunct(text=message)
        signed = self._account.sign_message(message_hash)
        return signed.signature.hex()
    
    def sign_typed_data(self, typed_data: Dict[str, Any]) -> str:
        """
        Sign typed data (EIP-712).
        
        Args:
            typed_data: Typed data dictionary (EIP-712 format).
            
        Returns:
            Signature as hex string.
        """
        from eth_account.messages import encode_structured_data
        encoded = encode_structured_data(typed_data)
        signed = self._account.sign_message(encoded)
        return signed.signature.hex()
    
    def verify_message(self, message: str, signature: str) -> bool:
        """
        Verify a signed message.
        
        Args:
            message: Original message.
            signature: Signature (hex string).
            
        Returns:
            True if signature is valid, False otherwise.
        """
        try:
            message_hash = encode_defunct(text=message)
            recovered = Account.recover_message(message_hash, signature=signature)
            return self.utils.is_same_address(recovered, self.address)
        except Exception as e:
            logger.error(f"Message verification failed: {e}")
            return False
    
    # ============ Transaction History ============
    
    def get_transaction_history(
        self,
        limit: int = 50,
        start_block: int = 0,
        end_block: int = 99999999,
        sort: str = 'desc'
    ) -> List[TransactionInfo]:
        """
        Get transaction history for this wallet.
        
        Args:
            limit: Maximum number of transactions.
            start_block: Starting block number.
            end_block: Ending block number.
            sort: Sort order ('asc' or 'desc').
            
        Returns:
            List of TransactionInfo objects.
        """
        # This would typically use Etherscan or a node with tx history
        # Simplified implementation using the web3 client's ability to fetch logs
        try:
            # Use etherscan-like method if available
            if hasattr(self.web3_client, 'get_transaction_history'):
                return self.web3_client.get_transaction_history(
                    self.address, start_block, end_block, sort, limit=limit
                )
            
            # Fallback: use logs for token transfers and basic transaction tracking
            # This is a simplified version - real implementation would use Etherscan API
            logger.warning("Transaction history retrieval not fully implemented")
            return []
        except Exception as e:
            logger.error(f"Failed to get transaction history: {e}")
            return []
    
    # ============ Keystore Management ============
    
    def encrypt_keystore(self, password: str, keystore_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Encrypt the private key into a keystore file.
        
        Args:
            password: Password to encrypt the key.
            keystore_path: Optional path to save the keystore.
            
        Returns:
            Keystore dictionary.
        """
        if not self._account:
            raise ValueError("No account to encrypt")
        
        keystore = Account.encrypt(self._account.key, password)
        
        if keystore_path:
            path = Path(keystore_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(keystore, f, indent=2)
            logger.info(f"Keystore saved to {path}")
        
        self._info.is_encrypted = True
        self.password = password
        
        return keystore
    
    def decrypt_keystore(self, keystore_data: Dict[str, Any], password: str) -> None:
        """
        Decrypt a keystore and import the account.
        
        Args:
            keystore_data: Keystore dictionary or file content.
            password: Password to decrypt.
        """
        try:
            self._account = Account.decrypt(keystore_data, password)
            self._info = WalletInfo(
                address=self._account.address,
                private_key=self._account.key.hex(),
                public_key=self._account.key.public_key.to_hex(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                network=self.network,
                chain_id=self.chain_id,
                is_encrypted=True
            )
            self.password = password
            logger.info(f"Decrypted keystore: {self._account.address}")
        except Exception as e:
            raise ValueError(f"Failed to decrypt keystore: {e}")
    
    # ============ Utility Methods ============
    
    def get_gas_estimate(self, to: str, amount: Union[float, int, str] = 0, data: Optional[str] = None) -> int:
        """
        Estimate gas for a transaction.
        
        Args:
            to: Recipient address.
            amount: Amount in ETH.
            data: Transaction data.
            
        Returns:
            Estimated gas limit.
        """
        tx = self.web3_client.build_transaction(
            to=to,
            value=amount,
            data=data,
            from_address=self.address
        )
        return self.web3_client.estimate_gas(tx)
    
    def get_token_gas_estimate(self, token_address: str, to: str, amount: Union[float, int, str]) -> int:
        """
        Estimate gas for an ERC20 transfer.
        
        Args:
            token_address: Token address.
            to: Recipient address.
            amount: Amount in token units.
            
        Returns:
            Estimated gas limit.
        """
        info = self.token_manager.get_token_info(token_address)
        amount_wei = int(Decimal(str(amount)) * (10 ** info.decimals))
        data = self.token_manager.multicall._encode_function_call(
            token_address, 'transfer', to, amount_wei
        )
        return self.get_gas_estimate(token_address, 0, data)
    
    def get_transaction_cost(self, to: str, amount: Union[float, int, str] = 0, data: Optional[str] = None) -> float:
        """
        Calculate the estimated transaction cost in ETH.
        
        Args:
            to: Recipient address.
            amount: Amount in ETH.
            data: Transaction data.
            
        Returns:
            Total cost in ETH (gas + amount).
        """
        gas = self.get_gas_estimate(to, amount, data)
        gas_price = self.gas_manager.get_gas_price_for_strategy('standard')
        cost_eth = self.utils.from_wei(gas * gas_price, 'ether')
        
        if isinstance(amount, (int, float)):
            cost_eth += amount
        else:
            cost_eth += float(amount)
        
        return cost_eth
    
    def get_token_transaction_cost(self, token_address: str, to: str, amount: Union[float, int, str]) -> float:
        """
        Calculate the estimated transaction cost for an ERC20 transfer in ETH.
        
        Args:
            token_address: Token address.
            to: Recipient address.
            amount: Amount in token units.
            
        Returns:
            Total cost in ETH (gas cost only).
        """
        gas = self.get_token_gas_estimate(token_address, to, amount)
        gas_price = self.gas_manager.get_gas_price_for_strategy('standard')
        return self.utils.from_wei(gas * gas_price, 'ether')
    
    def is_valid_address(self, address: str) -> bool:
        """Check if an address is valid."""
        return self.utils.is_valid_address(address)
    
    def to_checksum_address(self, address: str) -> str:
        """Convert to checksum address."""
        return self.utils.to_checksum_address(address)
    
    def get_network_name(self) -> str:
        """Get the current network name."""
        return self.network
    
    def get_chain_id(self) -> int:
        """Get the current chain ID."""
        return self.chain_id
    
    # ============ Export Methods ============
    
    def export_private_key(self) -> str:
        """Export the private key (hex string)."""
        if not self._info or not self._info.private_key:
            raise ValueError("Private key not available")
        return self._info.private_key
    
    def export_mnemonic(self) -> Optional[str]:
        """Export the mnemonic phrase (if available)."""
        return self._info.mnemonic if self._info else None
    
    def export_address(self) -> str:
        """Export the wallet address."""
        return self.address
    
    def export_info(self) -> Dict[str, Any]:
        """Export wallet information."""
        return {
            'address': self.address,
            'network': self.network,
            'chain_id': self.chain_id,
            'created_at': self._info.created_at.isoformat() if self._info else None,
            'balance': self.balance,
            'is_encrypted': self._info.is_encrypted if self._info else False,
        }
    
    # ============ Cache Management ============
    
    def clear_cache(self) -> None:
        """Clear the wallet cache."""
        if self._cache:
            self._cache.clear()
        logger.info("Wallet cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'cache_size': len(self._cache._cache) if self._cache else 0,
        }


def create_wallet(
    web3_client: Any,
    private_key: Optional[str] = None,
    mnemonic: Optional[str] = None,
    keystore_path: Optional[Union[str, Path]] = None,
    password: Optional[str] = None,
    network: str = "ethereum",
    **kwargs
) -> Web3Wallet:
    """
    Create a Web3 wallet instance.
    
    Args:
        web3_client: Web3 client instance.
        private_key: Private key to import.
        mnemonic: Mnemonic to import.
        keystore_path: Path to keystore file.
        password: Password for keystore.
        network: Network name.
        **kwargs: Additional arguments for Web3Wallet.
        
    Returns:
        Web3Wallet instance.
    """
    return Web3Wallet(
        web3_client=web3_client,
        private_key=private_key,
        mnemonic=mnemonic,
        keystore_path=keystore_path,
        password=password,
        network=network,
        **kwargs
    )


def create_random_wallet(web3_client: Any, network: str = "ethereum", **kwargs) -> Web3Wallet:
    """
    Create a new random wallet.
    
    Args:
        web3_client: Web3 client instance.
        network: Network name.
        **kwargs: Additional arguments for Web3Wallet.
        
    Returns:
        Web3Wallet instance.
    """
    return Web3Wallet(web3_client, network=network, **kwargs)


__all__ = [
    'WalletInfo',
    'TransactionInfo',
    'Web3Wallet',
    'create_wallet',
    'create_random_wallet',
]
