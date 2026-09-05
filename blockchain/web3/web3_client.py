"""
Web3 Client Module
===================

This module provides a high-level Web3 client for Ethereum and EVM-compatible blockchains.
It supports multiple providers, automatic failover, caching, and local transaction signing.
"""

import time
import json
import logging
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta

from web3 import Web3
from web3.middleware import geth_poa_middleware, http_retry_request_middleware
from web3.types import TxParams, Wei, HexBytes, BlockData, LogReceipt
from eth_account import Account
from eth_account.signers.local import LocalAccount
from hexbytes import HexBytes

from cachetools import TTLCache, cached

from trading.bots.swing_bot.utils.converters import to_int, to_float, to_str
from trading.bots.swing_bot.utils.validators import validate_data

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a blockchain provider."""
    name: str
    url: str
    is_websocket: bool = False
    weight: int = 1
    timeout: int = 30
    max_retries: int = 3


@dataclass
class Web3ClientConfig:
    """Configuration for the Web3 client."""
    providers: List[ProviderConfig] = field(default_factory=list)
    default_provider: Optional[str] = None
    cache_ttl_seconds: int = 60
    max_cache_items: int = 1000
    request_timeout: int = 30
    max_retries: int = 3


class Web3Client:
    """
    High-level Web3 client with provider management, caching, and signing.
    
    Supports multiple providers with automatic failover, local transaction signing,
    and caching of common calls.
    """
    
    # Minimal ERC-20 ABI for common operations
    ERC20_ABI = [
        {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
        {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "success", "type": "bool"}], "type": "function"},
        {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "success", "type": "bool"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "remaining", "type": "uint256"}], "type": "function"},
        {"constant": False, "inputs": [{"name": "_from", "type": "address"}, {"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "transferFrom", "outputs": [{"name": "success", "type": "bool"}], "type": "function"},
    ]
    
    def __init__(self, config: Union[Web3ClientConfig, Dict[str, Any]]):
        """
        Initialize the Web3 client.
        
        Args:
            config: Configuration dictionary or Web3ClientConfig instance.
        """
        if isinstance(config, dict):
            config = Web3ClientConfig(
                providers=[ProviderConfig(**p) for p in config.get('providers', [])],
                default_provider=config.get('default_provider'),
                cache_ttl_seconds=config.get('cache_ttl_seconds', 60),
                max_cache_items=config.get('max_cache_items', 1000),
                request_timeout=config.get('request_timeout', 30),
                max_retries=config.get('max_retries', 3),
            )
        self.config = config
        
        self._providers: Dict[str, Web3] = {}
        self._provider_configs: Dict[str, ProviderConfig] = {}
        self._active_provider_name: Optional[str] = None
        
        # Initialize providers
        for provider_config in self.config.providers:
            self._add_provider(provider_config)
        
        # Set default provider
        if self.config.default_provider:
            self._active_provider_name = self.config.default_provider
        elif self._provider_configs:
            self._active_provider_name = list(self._provider_configs.keys())[0]
        
        # Cache for contract ABIs and other data
        self._cache = TTLCache(
            maxsize=self.config.max_cache_items,
            ttl=self.config.cache_ttl_seconds
        )
        
        # Local account for signing
        self._account: Optional[LocalAccount] = None
        
        # Connection status
        self._connected = False
        self._check_connection()
    
    def _add_provider(self, config: ProviderConfig) -> None:
        """
        Add a provider to the client.
        
        Args:
            config: Provider configuration.
        """
        if config.is_websocket:
            w3 = Web3(Web3.WebsocketProvider(
                config.url,
                websocket_timeout=config.timeout,
                websocket_kwargs={'max_size': 2**26}
            ))
        else:
            w3 = Web3(Web3.HTTPProvider(
                config.url,
                request_kwargs={'timeout': config.timeout}
            ))
        # Inject middleware
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        if config.max_retries > 1:
            w3.middleware_onion.add(http_retry_request_middleware)
        
        self._providers[config.name] = w3
        self._provider_configs[config.name] = config
    
    def _check_connection(self) -> bool:
        """
        Check if the active provider is connected.
        
        Returns:
            True if connected, False otherwise.
        """
        w3 = self._get_active_web3()
        if w3 is None:
            self._connected = False
            return False
        
        try:
            self._connected = w3.is_connected()
        except Exception:
            self._connected = False
        
        if not self._connected:
            # Try to failover
            self._failover()
        
        return self._connected
    
    def _failover(self) -> bool:
        """
        Attempt to failover to the next available provider.
        
        Returns:
            True if a provider is connected, False otherwise.
        """
        for name in self._provider_configs.keys():
            if name == self._active_provider_name:
                continue
            w3 = self._providers.get(name)
            if w3 and w3.is_connected():
                self._active_provider_name = name
                self._connected = True
                logger.info(f"Failed over to provider: {name}")
                return True
        
        self._connected = False
        logger.error("All providers are down")
        return False
    
    def _get_active_web3(self) -> Optional[Web3]:
        """
        Get the active Web3 instance.
        
        Returns:
            Web3 instance or None if no provider is active.
        """
        if self._active_provider_name is None:
            return None
        return self._providers.get(self._active_provider_name)
    
    def _call_with_failover(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call a function with automatic failover.
        
        Args:
            func: The function to call (bound to Web3 instance).
            *args, **kwargs: Arguments for the function.
            
        Returns:
            Result of the function call.
            
        Raises:
            Exception: If all providers fail.
        """
        if not self._connected:
            self._check_connection()
        
        w3 = self._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active provider")
        
        try:
            return func(w3, *args, **kwargs)
        except Exception as e:
            logger.warning(f"Provider {self._active_provider_name} failed: {e}")
            if self._failover():
                # Retry with new provider
                w3 = self._get_active_web3()
                if w3 is not None:
                    return func(w3, *args, **kwargs)
            raise ConnectionError("All providers failed") from e
    
    # ============ Connection & Account ============
    
    def set_private_key(self, private_key: str) -> None:
        """
        Set the private key for signing transactions.
        
        Args:
            private_key: Private key in hex format (with or without 0x prefix).
        """
        self._account = Account.from_key(private_key)
    
    @property
    def address(self) -> Optional[str]:
        """Get the address associated with the private key."""
        return self._account.address if self._account else None
    
    @property
    def chain_id(self) -> int:
        """Get the chain ID of the active network."""
        w3 = self._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active provider")
        return self._call_with_failover(lambda w: w.eth.chain_id)
    
    # ============ Account Methods ============
    
    def get_balance(self, address: Optional[str] = None) -> float:
        """
        Get the ETH balance for an address.
        
        Args:
            address: Ethereum address (defaults to the account address if set).
            
        Returns:
            Balance in ETH as float.
        """
        if address is None:
            if not self._account:
                raise ValueError("No address provided and no private key set")
            address = self._account.address
        
        wei = self._call_with_failover(lambda w: w.eth.get_balance(address))
        return wei / 1e18
    
    def get_token_balance(
        self,
        token_address: str,
        address: Optional[str] = None,
        decimals: Optional[int] = None
    ) -> float:
        """
        Get the ERC-20 token balance for an address.
        
        Args:
            token_address: Token contract address.
            address: Wallet address (defaults to account address).
            decimals: Token decimals (auto-fetched if None).
            
        Returns:
            Token balance in token units.
        """
        if address is None:
            if not self._account:
                raise ValueError("No address provided and no private key set")
            address = self._account.address
        
        if decimals is None:
            decimals = self.get_token_decimals(token_address) or 18
        
        balance = self.call_contract_function(token_address, 'balanceOf', address, abi=self.ERC20_ABI)
        if balance is None:
            return 0.0
        
        return balance / (10 ** decimals)
    
    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """
        Get ERC-20 token information.
        
        Args:
            token_address: Token contract address.
            
        Returns:
            Dictionary with name, symbol, decimals, totalSupply.
        """
        info = {}
        
        try:
            info['name'] = self.call_contract_function(token_address, 'name', abi=self.ERC20_ABI)
        except:
            info['name'] = 'Unknown'
        
        try:
            info['symbol'] = self.call_contract_function(token_address, 'symbol', abi=self.ERC20_ABI)
        except:
            info['symbol'] = 'Unknown'
        
        try:
            info['decimals'] = self.call_contract_function(token_address, 'decimals', abi=self.ERC20_ABI) or 18
        except:
            info['decimals'] = 18
        
        try:
            total = self.call_contract_function(token_address, 'totalSupply', abi=self.ERC20_ABI)
            info['total_supply'] = total / (10 ** info['decimals']) if total else 0
        except:
            info['total_supply'] = 0
        
        return info
    
    def get_token_decimals(self, token_address: str) -> int:
        """
        Get the decimals of an ERC-20 token.
        
        Args:
            token_address: Token contract address.
            
        Returns:
            Number of decimals.
        """
        return self.call_contract_function(token_address, 'decimals', abi=self.ERC20_ABI) or 18
    
    # ============ Transaction Methods ============
    
    def send_transaction(
        self,
        to: str,
        value: Union[float, int, str],
        data: Optional[str] = None,
        gas: Optional[int] = None,
        gas_price: Optional[int] = None,
        nonce: Optional[int] = None,
        max_fee_per_gas: Optional[int] = None,
        max_priority_fee_per_gas: Optional[int] = None,
        from_address: Optional[str] = None
    ) -> str:
        """
        Send an ETH transaction.
        
        Args:
            to: Recipient address.
            value: Amount in ETH (float).
            data: Transaction data (hex string).
            gas: Gas limit (auto-estimated if None).
            gas_price: Gas price in wei (legacy).
            nonce: Transaction nonce (auto-fetched if None).
            max_fee_per_gas: Max fee per gas for EIP-1559.
            max_priority_fee_per_gas: Max priority fee for EIP-1559.
            from_address: Sender address (defaults to account address).
            
        Returns:
            Transaction hash as hex string.
        """
        if not self._account:
            raise ValueError("Private key not set")
        
        if from_address is None:
            from_address = self._account.address
        
        w3 = self._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active provider")
        
        # Build transaction
        tx: TxParams = {
            'from': from_address,
            'to': to,
            'value': Web3.to_wei(value, 'ether'),
            'nonce': nonce if nonce is not None else self._call_with_failover(lambda w: w.eth.get_transaction_count(from_address)),
        }
        
        if data:
            tx['data'] = data
        
        # Fee strategy
        if max_fee_per_gas is not None and max_priority_fee_per_gas is not None:
            tx['maxFeePerGas'] = max_fee_per_gas
            tx['maxPriorityFeePerGas'] = max_priority_fee_per_gas
            tx['type'] = '0x2'
        elif gas_price is not None:
            tx['gasPrice'] = gas_price
        else:
            # Auto-detect
            if w3.eth.max_priority_fee is not None:
                base_fee = self._call_with_failover(lambda w: w.eth.get_block('pending')['baseFeePerGas']) or 0
                max_priority = w3.eth.max_priority_fee
                tx['maxFeePerGas'] = base_fee + max_priority * 2
                tx['maxPriorityFeePerGas'] = max_priority
                tx['type'] = '0x2'
            else:
                tx['gasPrice'] = self._call_with_failover(lambda w: w.eth.gas_price)
        
        # Gas limit
        if gas is None:
            tx['gas'] = self._call_with_failover(lambda w: w.eth.estimate_gas(tx))
        else:
            tx['gas'] = gas
        
        # Sign and send
        signed = self._account.sign_transaction(tx)
        tx_hash = self._call_with_failover(lambda w: w.eth.send_raw_transaction(signed.raw_transaction))
        return tx_hash.hex()
    
    def send_erc20_transaction(
        self,
        token_address: str,
        to: str,
        amount: Union[float, int, str],
        decimals: Optional[int] = None,
        gas: Optional[int] = None,
        gas_price: Optional[int] = None,
        nonce: Optional[int] = None,
        max_fee_per_gas: Optional[int] = None,
        max_priority_fee_per_gas: Optional[int] = None,
        from_address: Optional[str] = None
    ) -> str:
        """
        Send an ERC-20 token transfer transaction.
        
        Args:
            token_address: Token contract address.
            to: Recipient address.
            amount: Amount in token units (float).
            decimals: Token decimals (auto-fetched if None).
            gas: Gas limit.
            gas_price: Gas price in wei.
            nonce: Transaction nonce.
            max_fee_per_gas: Max fee per gas for EIP-1559.
            max_priority_fee_per_gas: Max priority fee.
            from_address: Sender address (defaults to account address).
            
        Returns:
            Transaction hash as hex string.
        """
        if not self._account:
            raise ValueError("Private key not set")
        
        if from_address is None:
            from_address = self._account.address
        
        if decimals is None:
            decimals = self.get_token_decimals(token_address) or 18
        
        amount_wei = int(Decimal(str(amount)) * (10 ** decimals))
        
        # Encode transfer
        data = self.encode_function_call(
            token_address,
            'transfer',
            to,
            amount_wei,
            abi=self.ERC20_ABI
        )
        
        return self.send_transaction(
            to=token_address,
            value=0,
            data=data,
            gas=gas,
            gas_price=gas_price,
            nonce=nonce,
            max_fee_per_gas=max_fee_per_gas,
            max_priority_fee_per_gas=max_priority_fee_per_gas,
            from_address=from_address
        )
    
    def get_transaction_receipt(self, tx_hash: str) -> Dict[str, Any]:
        """
        Get the receipt of a transaction.
        
        Args:
            tx_hash: Transaction hash.
            
        Returns:
            Transaction receipt as dict.
        """
        receipt = self._call_with_failover(lambda w: w.eth.get_transaction_receipt(tx_hash))
        if receipt is None:
            return {}
        
        return {
            'transaction_hash': receipt['transactionHash'].hex(),
            'transaction_index': receipt['transactionIndex'],
            'block_hash': receipt['blockHash'].hex(),
            'block_number': receipt['blockNumber'],
            'cumulative_gas_used': receipt['cumulativeGasUsed'],
            'gas_used': receipt['gasUsed'],
            'contract_address': receipt['contractAddress'],
            'status': receipt['status'],
            'logs': self._parse_logs(receipt['logs'])
        }
    
    def wait_for_transaction_receipt(self, tx_hash: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Wait for a transaction receipt.
        
        Args:
            tx_hash: Transaction hash.
            timeout: Maximum time to wait in seconds.
            
        Returns:
            Transaction receipt as dict.
        """
        receipt = self._call_with_failover(lambda w: w.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout))
        if receipt is None:
            return {}
        
        return {
            'transaction_hash': receipt['transactionHash'].hex(),
            'transaction_index': receipt['transactionIndex'],
            'block_hash': receipt['blockHash'].hex(),
            'block_number': receipt['blockNumber'],
            'cumulative_gas_used': receipt['cumulativeGasUsed'],
            'gas_used': receipt['gasUsed'],
            'contract_address': receipt['contractAddress'],
            'status': receipt['status'],
            'logs': self._parse_logs(receipt['logs'])
        }
    
    # ============ Contract Methods ============
    
    def call_contract_function(
        self,
        contract_address: str,
        function_name: str,
        *args,
        abi: Optional[List[Dict[str, Any]]] = None
    ) -> Any:
        """
        Call a read-only contract function.
        
        Args:
            contract_address: Contract address.
            function_name: Function name.
            *args: Function arguments.
            abi: Contract ABI (uses ERC-20 ABI if None).
            
        Returns:
            Function return value.
        """
        if abi is None:
            abi = self.ERC20_ABI
        
        w3 = self._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active provider")
        
        contract = w3.eth.contract(address=contract_address, abi=abi)
        function = getattr(contract.functions, function_name)
        result = function(*args).call()
        return result
    
    def encode_function_call(
        self,
        contract_address: str,
        function_name: str,
        *args,
        abi: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Encode a contract function call for a transaction.
        
        Args:
            contract_address: Contract address.
            function_name: Function name.
            *args: Function arguments.
            abi: Contract ABI (uses ERC-20 ABI if None).
            
        Returns:
            Hex-encoded transaction data.
        """
        if abi is None:
            abi = self.ERC20_ABI
        
        w3 = self._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active provider")
        
        contract = w3.eth.contract(address=contract_address, abi=abi)
        function = getattr(contract.functions, function_name)
        tx = function(*args).build_transaction({'from': self.address or '0x0000000000000000000000000000000000000000'})
        return tx['data'].hex()
    
    # ============ Block Methods ============
    
    def get_block(self, block_identifier: Union[int, str] = 'latest') -> Dict[str, Any]:
        """
        Get block information.
        
        Args:
            block_identifier: Block number, 'latest', 'pending', or 'earliest'.
            
        Returns:
            Block data as dictionary.
        """
        block = self._call_with_failover(lambda w: w.eth.get_block(block_identifier))
        return {
            'number': block['number'],
            'hash': block['hash'].hex(),
            'parent_hash': block['parentHash'].hex(),
            'timestamp': block['timestamp'],
            'transactions': [tx.hex() if isinstance(tx, HexBytes) else tx for tx in block['transactions']],
            'gas_used': block['gasUsed'],
            'gas_limit': block['gasLimit'],
            'base_fee_per_gas': block.get('baseFeePerGas', 0),
        }
    
    def get_block_number(self) -> int:
        """Get the current block number."""
        return self._call_with_failover(lambda w: w.eth.block_number)
    
    # ============ Logs / Events ============
    
    def get_logs(
        self,
        from_block: Union[int, str] = 'earliest',
        to_block: Union[int, str] = 'latest',
        address: Optional[str] = None,
        topics: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get logs (events) matching filters.
        
        Args:
            from_block: Starting block.
            to_block: Ending block.
            address: Contract address.
            topics: List of topics to filter.
            
        Returns:
            List of log entries.
        """
        logs = self._call_with_failover(
            lambda w: w.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': address,
                'topics': topics
            })
        )
        return self._parse_logs(logs)
    
    def _parse_logs(self, logs: List[LogReceipt]) -> List[Dict[str, Any]]:
        """Parse log entries into dictionaries."""
        result = []
        for log in logs:
            result.append({
                'address': log['address'],
                'data': log['data'].hex(),
                'topics': [t.hex() for t in log['topics']],
                'block_number': log['blockNumber'],
                'block_hash': log['blockHash'].hex(),
                'transaction_hash': log['transactionHash'].hex(),
                'transaction_index': log['transactionIndex'],
                'log_index': log['logIndex'],
                'removed': log['removed'],
            })
        return result
    
    # ============ Gas Methods ============
    
    def get_gas_price(self) -> int:
        """Get current gas price in wei."""
        return self._call_with_failover(lambda w: w.eth.gas_price)
    
    def get_gas_price_gwei(self) -> float:
        """Get current gas price in Gwei."""
        return self.get_gas_price() / 1e9
    
    def get_max_priority_fee(self) -> int:
        """Get current max priority fee (tip) in wei."""
        return self._call_with_failover(lambda w: w.eth.max_priority_fee)
    
    def estimate_gas(self, tx: Dict[str, Any]) -> int:
        """Estimate gas for a transaction."""
        return self._call_with_failover(lambda w: w.eth.estimate_gas(tx))
    
    # ============ ENS Methods ============
    
    def resolve_ens(self, name: str) -> Optional[str]:
        """
        Resolve an ENS name to an address.
        
        Args:
            name: ENS name (e.g., 'vitalik.eth').
            
        Returns:
            Address or None if not found.
        """
        return self._call_with_failover(lambda w: w.ens.address(name))
    
    def reverse_resolve_ens(self, address: str) -> Optional[str]:
        """
        Resolve an address to an ENS name.
        
        Args:
            address: Ethereum address.
            
        Returns:
            ENS name or None if not found.
        """
        return self._call_with_failover(lambda w: w.ens.name(address))
    
    # ============ Utility Methods ============
    
    def to_checksum_address(self, address: str) -> str:
        """Convert an address to checksum format."""
        return Web3.to_checksum_address(address)
    
    def is_address(self, address: str) -> bool:
        """Check if a string is a valid Ethereum address."""
        return Web3.is_address(address)
    
    def is_checksum_address(self, address: str) -> bool:
        """Check if an address is checksummed."""
        return Web3.is_checksum_address(address)
    
    def to_wei(self, amount: Union[float, int, str], unit: str = 'ether') -> int:
        """Convert an amount to wei."""
        return Web3.to_wei(amount, unit)
    
    def from_wei(self, amount: int, unit: str = 'ether') -> float:
        """Convert wei to another unit."""
        return Web3.from_wei(amount, unit)
    
    def close(self) -> None:
        """Close WebSocket connections if any."""
        for name, w3 in self._providers.items():
            if hasattr(w3.provider, 'close'):
                try:
                    w3.provider.close()
                except Exception:
                    pass
    
    # ============ Caching ============
    
    @cached(cache=TTLCache(maxsize=100, ttl=3600))
    def _get_cached_token_info(self, token_address: str) -> Dict[str, Any]:
        """Cached token info."""
        return self.get_token_info(token_address)
    
    def get_token_info_cached(self, token_address: str) -> Dict[str, Any]:
        """Get token info with caching."""
        return self._get_cached_token_info(token_address)


def create_web3_client(config: Dict[str, Any]) -> Web3Client:
    """
    Create a Web3 client from configuration.
    
    Args:
        config: Configuration dictionary.
        
    Returns:
        Web3Client instance.
    """
    return Web3Client(config)


__all__ = [
    'ProviderConfig',
    'Web3ClientConfig',
    'Web3Client',
    'create_web3_client'
]
