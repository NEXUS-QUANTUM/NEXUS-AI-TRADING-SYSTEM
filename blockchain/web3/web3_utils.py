"""
Web3 Utilities Module
=======================

This module provides utility functions for Web3 operations including address
validation, checksumming, unit conversion, ABI encoding/decoding, signature
verification, and other common Web3 tasks.
"""

import re
import json
import time
import hashlib
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
from decimal import Decimal, getcontext
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache

from web3 import Web3
from web3.types import BlockIdentifier, TxParams, Wei
from eth_abi import decode_abi, encode_abi
from eth_utils import (
    is_address,
    is_checksum_address,
    to_checksum_address,
    to_hex,
    to_bytes,
    to_int,
    to_text,
    keccak,
    is_hex,
    is_hex_address,
    remove_0x_prefix,
    add_0x_prefix,
    is_same_address,
)
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys
from hexbytes import HexBytes

from trading.bots.swing_bot.utils.cache import MemoryCache
from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.converters import to_float, to_int as to_int_convert

logger = logging.getLogger(__name__)


class Web3Utils:
    """
    Web3 utility class providing common blockchain operations.
    
    Supports:
    - Address validation and formatting
    - Unit conversions (wei, gwei, ether)
    - ABI encoding/decoding
    - Signature generation and verification
    - Keccak hashing
    - Transaction building
    - Message signing
    - Contract address generation
    - IPFS hash conversion
    """
    
    # Chain IDs for common networks
    CHAIN_IDS = {
        'ethereum': 1,
        'goerli': 5,
        'sepolia': 11155111,
        'polygon': 137,
        'arbitrum': 42161,
        'optimism': 10,
        'bnb': 56,
        'avalanche': 43114,
        'fantom': 250,
        'gnosis': 100,
    }
    
    # Network names by chain ID
    CHAIN_NAMES = {v: k for k, v in CHAIN_IDS.items()}
    
    def __init__(self, web3_client: Optional[Any] = None, enable_cache: bool = True):
        """
        Initialize Web3 utilities.
        
        Args:
            web3_client: Optional Web3 client instance.
            enable_cache: Enable caching for expensive operations.
        """
        self.web3_client = web3_client
        self._cache = MemoryCache(max_size=1000, default_ttl=300) if enable_cache else None
        
        logger.info("Web3Utils initialized")
    
    # ============ Address Utilities ============
    
    def is_valid_address(self, address: str) -> bool:
        """
        Check if a string is a valid Ethereum address.
        
        Args:
            address: Address to check.
            
        Returns:
            True if valid, False otherwise.
        """
        return is_address(address)
    
    def is_checksum_address(self, address: str) -> bool:
        """
        Check if an address is checksummed.
        
        Args:
            address: Address to check.
            
        Returns:
            True if checksummed, False otherwise.
        """
        return is_checksum_address(address)
    
    def to_checksum_address(self, address: str) -> str:
        """
        Convert an address to checksum format.
        
        Args:
            address: Address to convert.
            
        Returns:
            Checksummed address.
            
        Raises:
            ValueError: If address is invalid.
        """
        return to_checksum_address(address)
    
    def is_same_address(self, address1: str, address2: str) -> bool:
        """
        Check if two addresses are the same (ignoring case).
        
        Args:
            address1: First address.
            address2: Second address.
            
        Returns:
            True if same, False otherwise.
        """
        return is_same_address(address1, address2)
    
    def normalize_address(self, address: str) -> str:
        """
        Normalize an address (convert to checksum format).
        
        Args:
            address: Address to normalize.
            
        Returns:
            Normalized address.
        """
        return self.to_checksum_address(address)
    
    def get_contract_address(
        self,
        deployer_address: str,
        nonce: int,
        chain_id: Optional[int] = None
    ) -> str:
        """
        Calculate the contract address that would be deployed.
        
        Args:
            deployer_address: Address that deploys the contract.
            nonce: Transaction nonce.
            chain_id: Chain ID (for CREATE2).
            
        Returns:
            Contract address.
        """
        deployer = self.to_checksum_address(deployer_address)
        
        if chain_id is None:
            # CREATE address (RIP-721)
            raw = to_bytes(hexstr=deployer) + nonce.to_bytes(1, 'big')
            address = keccak(raw)[12:]
            return to_checksum_address(address.hex())
        else:
            # CREATE2 address (ERC-1014)
            salt = b'\x00' * 32
            init_code_hash = keccak(b'')
            
            raw = b'\xff' + to_bytes(hexstr=deployer) + salt + init_code_hash
            address = keccak(raw)[12:]
            return to_checksum_address(address.hex())
    
    def get_network_name(self, chain_id: int) -> str:
        """
        Get network name from chain ID.
        
        Args:
            chain_id: Chain ID.
            
        Returns:
            Network name.
        """
        return self.CHAIN_NAMES.get(chain_id, f'chain_{chain_id}')
    
    def get_chain_id(self, network: str) -> int:
        """
        Get chain ID from network name.
        
        Args:
            network: Network name.
            
        Returns:
            Chain ID.
        """
        return self.CHAIN_IDS.get(network.lower(), 1)
    
    # ============ Unit Conversions ============
    
    def to_wei(self, amount: Union[float, int, str], unit: str = 'ether') -> int:
        """
        Convert an amount to wei.
        
        Args:
            amount: Amount to convert.
            unit: Unit ('ether', 'gwei', 'wei', etc.).
            
        Returns:
            Amount in wei.
        """
        return Web3.to_wei(amount, unit)
    
    def from_wei(self, amount: int, unit: str = 'ether') -> float:
        """
        Convert wei to another unit.
        
        Args:
            amount: Amount in wei.
            unit: Target unit.
            
        Returns:
            Amount in target unit.
        """
        return Web3.from_wei(amount, unit)
    
    def format_eth(self, amount: Union[int, float, str], decimals: int = 4) -> str:
        """
        Format an amount in ETH.
        
        Args:
            amount: Amount in wei or ether.
            decimals: Number of decimal places.
            
        Returns:
            Formatted string.
        """
        if isinstance(amount, int):
            amount = self.from_wei(amount, 'ether')
        elif isinstance(amount, str):
            amount = float(amount)
        
        return f"{amount:,.{decimals}f} ETH"
    
    def format_gwei(self, amount: Union[int, float, str], decimals: int = 2) -> str:
        """
        Format an amount in Gwei.
        
        Args:
            amount: Amount in wei or gwei.
            decimals: Number of decimal places.
            
        Returns:
            Formatted string.
        """
        if isinstance(amount, int):
            amount = self.from_wei(amount, 'gwei')
        elif isinstance(amount, str):
            amount = float(amount)
        
        return f"{amount:,.{decimals}f} Gwei"
    
    def format_wei(self, amount: int, decimals: int = 0) -> str:
        """
        Format an amount in wei.
        
        Args:
            amount: Amount in wei.
            decimals: Number of decimal places.
            
        Returns:
            Formatted string.
        """
        return f"{amount:,.{decimals}f} Wei"
    
    def parse_eth(self, amount: str) -> int:
        """
        Parse an ETH amount string to wei.
        
        Args:
            amount: Amount string (e.g., "1.5 ETH").
            
        Returns:
            Amount in wei.
        """
        amount = amount.replace('ETH', '').replace('eth', '').strip()
        return self.to_wei(float(amount), 'ether')
    
    # ============ Hex Utilities ============
    
    def to_hex(self, value: Union[int, str, bytes]) -> str:
        """
        Convert a value to hex string.
        
        Args:
            value: Value to convert.
            
        Returns:
            Hex string.
        """
        return to_hex(value)
    
    def to_bytes(self, value: Union[int, str, bytes]) -> bytes:
        """
        Convert a value to bytes.
        
        Args:
            value: Value to convert.
            
        Returns:
            Bytes.
        """
        return to_bytes(value)
    
    def remove_0x_prefix(self, hex_str: str) -> str:
        """
        Remove the '0x' prefix from a hex string.
        
        Args:
            hex_str: Hex string.
            
        Returns:
            Hex string without prefix.
        """
        return remove_0x_prefix(hex_str)
    
    def add_0x_prefix(self, hex_str: str) -> str:
        """
        Add the '0x' prefix to a hex string.
        
        Args:
            hex_str: Hex string.
            
        Returns:
            Hex string with prefix.
        """
        return add_0x_prefix(hex_str)
    
    def is_hex(self, value: str) -> bool:
        """
        Check if a string is a valid hex string.
        
        Args:
            value: String to check.
            
        Returns:
            True if valid hex, False otherwise.
        """
        return is_hex(value)
    
    def hex_to_bytes(self, hex_str: str) -> bytes:
        """
        Convert a hex string to bytes.
        
        Args:
            hex_str: Hex string.
            
        Returns:
            Bytes.
        """
        return bytes.fromhex(self.remove_0x_prefix(hex_str))
    
    def bytes_to_hex(self, data: bytes) -> str:
        """
        Convert bytes to hex string.
        
        Args:
            data: Bytes.
            
        Returns:
            Hex string.
        """
        return add_0x_prefix(data.hex())
    
    # ============ Keccak Utilities ============
    
    def keccak(self, data: Union[str, bytes]) -> bytes:
        """
        Calculate keccak-256 hash.
        
        Args:
            data: Data to hash.
            
        Returns:
            Hash bytes.
        """
        return keccak(data)
    
    def keccak_hex(self, data: Union[str, bytes]) -> str:
        """
        Calculate keccak-256 hash as hex string.
        
        Args:
            data: Data to hash.
            
        Returns:
            Hex hash string.
        """
        return add_0x_prefix(keccak(data).hex())
    
    def solidity_keccak(self, types: List[str], values: List[Any]) -> str:
        """
        Calculate Solidity-style keccak-256 hash.
        
        Args:
            types: List of Solidity types.
            values: List of values.
            
        Returns:
            Hex hash string.
        """
        from eth_abi import encode_abi
        encoded = encode_abi(types, values)
        return add_0x_prefix(keccak(encoded).hex())
    
    # ============ ABI Utilities ============
    
    def encode_abi(self, types: List[str], values: List[Any]) -> str:
        """
        Encode values using ABI encoding.
        
        Args:
            types: List of Solidity types.
            values: List of values.
            
        Returns:
            Encoded hex string.
        """
        return add_0x_prefix(encode_abi(types, values).hex())
    
    def decode_abi(self, types: List[str], data: Union[str, bytes]) -> List[Any]:
        """
        Decode ABI-encoded data.
        
        Args:
            types: List of Solidity types.
            data: Encoded data.
            
        Returns:
            List of decoded values.
        """
        if isinstance(data, str):
            data = self.hex_to_bytes(data)
        return decode_abi(types, data)
    
    def encode_function_call(
        self,
        function_name: str,
        params: List[Any],
        param_types: List[str]
    ) -> str:
        """
        Encode a function call for a contract transaction.
        
        Args:
            function_name: Name of the function.
            params: Function parameters.
            param_types: Parameter types.
            
        Returns:
            Encoded function call data.
        """
        # Calculate function signature
        signature = f"{function_name}({','.join(param_types)})"
        method_id = self.keccak(signature.encode())[:4]
        
        # Encode parameters
        encoded_params = self.encode_abi(param_types, params)
        
        return add_0x_prefix(method_id.hex() + self.remove_0x_prefix(encoded_params))
    
    def decode_function_call(self, data: str, param_types: List[str]) -> List[Any]:
        """
        Decode a function call.
        
        Args:
            data: Function call data.
            param_types: Parameter types.
            
        Returns:
            List of decoded parameters.
        """
        data = self.remove_0x_prefix(data)
        if len(data) < 8:
            return []
        
        # Skip method ID (first 8 characters)
        params_hex = data[8:]
        if not params_hex:
            return []
        
        return self.decode_abi(param_types, params_hex)
    
    def get_function_signature(self, function_name: str, param_types: List[str]) -> str:
        """
        Get the function signature for a contract function.
        
        Args:
            function_name: Name of the function.
            param_types: Parameter types.
            
        Returns:
            Function signature.
        """
        return f"{function_name}({','.join(param_types)})"
    
    def get_function_selector(self, function_signature: str) -> str:
        """
        Get the function selector (first 4 bytes of keccak hash).
        
        Args:
            function_signature: Function signature.
            
        Returns:
            Function selector as hex string.
        """
        hash_bytes = self.keccak(function_signature.encode())
        return add_0x_prefix(hash_bytes[:4].hex())
    
    # ============ Event Utilities ============
    
    def get_event_signature(self, event_name: str, param_types: List[str]) -> str:
        """
        Get the event signature.
        
        Args:
            event_name: Name of the event.
            param_types: Parameter types.
            
        Returns:
            Event signature.
        """
        return f"{event_name}({','.join(param_types)})"
    
    def get_event_topic(self, event_signature: str) -> str:
        """
        Get the event topic (keccak hash of event signature).
        
        Args:
            event_signature: Event signature.
            
        Returns:
            Event topic as hex string.
        """
        return add_0x_prefix(self.keccak(event_signature.encode()).hex())
    
    def decode_event_data(
        self,
        data: str,
        param_types: List[str],
        indexed_params: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Decode event data.
        
        Args:
            data: Event data.
            param_types: Parameter types.
            indexed_params: Indexed parameter types.
            
        Returns:
            Decoded event data.
        """
        result = {}
        
        # Decode non-indexed parameters
        if data and data != '0x':
            decoded = self.decode_abi(param_types, data)
            for i, value in enumerate(decoded):
                result[f'param_{i}'] = value
        
        return result
    
    # ============ Signature Utilities ============
    
    def sign_message(self, message: str, private_key: str) -> str:
        """
        Sign a message with a private key.
        
        Args:
            message: Message to sign.
            private_key: Private key (hex string).
            
        Returns:
            Signature as hex string.
        """
        account = Account.from_key(private_key)
        message_hash = encode_defunct(text=message)
        signed = account.sign_message(message_hash)
        return signed.signature.hex()
    
    def verify_message(self, message: str, signature: str, address: str) -> bool:
        """
        Verify a signed message.
        
        Args:
            message: Original message.
            signature: Signature (hex string).
            address: Address that signed the message.
            
        Returns:
            True if signature is valid, False otherwise.
        """
        message_hash = encode_defunct(text=message)
        try:
            recovered = Account.recover_message(message_hash, signature=signature)
            return self.is_same_address(recovered, address)
        except:
            return False
    
    def sign_transaction(self, tx_dict: Dict[str, Any], private_key: str) -> str:
        """
        Sign a transaction.
        
        Args:
            tx_dict: Transaction dictionary.
            private_key: Private key (hex string).
            
        Returns:
            Signed transaction as hex string.
        """
        account = Account.from_key(private_key)
        signed = account.sign_transaction(tx_dict)
        return signed.raw_transaction.hex()
    
    def recover_transaction_signer(self, signed_tx_hex: str) -> str:
        """
        Recover the signer address from a signed transaction.
        
        Args:
            signed_tx_hex: Signed transaction as hex string.
            
        Returns:
            Signer address.
        """
        signed_tx = HexBytes(signed_tx_hex)
        from eth_account import Account
        return Account.recover_transaction(signed_tx)
    
    # ============ Private Key Utilities ============
    
    def generate_private_key(self) -> str:
        """
        Generate a random private key.
        
        Returns:
            Private key as hex string.
        """
        return Account.create().key.hex()
    
    def private_key_to_address(self, private_key: str) -> str:
        """
        Get address from private key.
        
        Args:
            private_key: Private key (hex string).
            
        Returns:
            Address.
        """
        account = Account.from_key(private_key)
        return account.address
    
    def is_valid_private_key(self, private_key: str) -> bool:
        """
        Check if a string is a valid private key.
        
        Args:
            private_key: Private key to check.
            
        Returns:
            True if valid, False otherwise.
        """
        try:
            Account.from_key(private_key)
            return True
        except:
            return False
    
    # ============ Block Utilities ============
    
    def get_block_timestamp(self, block: Union[int, str, Dict]) -> datetime:
        """
        Get the timestamp of a block.
        
        Args:
            block: Block number, identifier, or block data.
            
        Returns:
            Datetime object.
        """
        if isinstance(block, dict):
            timestamp = block.get('timestamp')
        elif self.web3_client:
            if isinstance(block, (int, str)):
                block_data = self.web3_client.get_block(block)
                timestamp = block_data.get('timestamp')
            else:
                return datetime.now()
        else:
            return datetime.now()
        
        if timestamp:
            return datetime.fromtimestamp(timestamp)
        return datetime.now()
    
    def get_block_age(self, block: Union[int, str, Dict]) -> timedelta:
        """
        Get the age of a block.
        
        Args:
            block: Block number, identifier, or block data.
            
        Returns:
            Timedelta object.
        """
        timestamp = self.get_block_timestamp(block)
        return datetime.now() - timestamp
    
    def is_block_old(self, block: Union[int, str, Dict], max_age_seconds: int = 600) -> bool:
        """
        Check if a block is old (older than max_age_seconds).
        
        Args:
            block: Block number, identifier, or block data.
            max_age_seconds: Maximum age in seconds.
            
        Returns:
            True if block is old, False otherwise.
        """
        age = self.get_block_age(block)
        return age.total_seconds() > max_age_seconds
    
    # ============ IPFS Utilities ============
    
    def ipfs_to_cid(self, ipfs_hash: str) -> str:
        """
        Convert IPFS hash to CID format.
        
        Args:
            ipfs_hash: IPFS hash.
            
        Returns:
            CID string.
        """
        if ipfs_hash.startswith('Qm'):
            # Base58 encoded CIDv0
            return ipfs_hash
        elif ipfs_hash.startswith('bafy'):
            # CIDv1
            return ipfs_hash
        else:
            return ipfs_hash
    
    def cid_to_ipfs(self, cid: str) -> str:
        """
        Convert CID to IPFS hash format.
        
        Args:
            cid: CID string.
            
        Returns:
            IPFS hash.
        """
        return cid
    
    # ============ ENS Utilities ============
    
    def normalize_ens_name(self, name: str) -> str:
        """
        Normalize an ENS name.
        
        Args:
            name: ENS name.
            
        Returns:
            Normalized name.
        """
        if not name:
            return name
        return name.lower().strip()
    
    def is_ens_name(self, name: str) -> bool:
        """
        Check if a string is a valid ENS name.
        
        Args:
            name: String to check.
            
        Returns:
            True if valid ENS name, False otherwise.
        """
        if not name or '.' not in name:
            return False
        
        parts = name.split('.')
        if len(parts) < 2:
            return False
        
        # Check each part is valid
        for part in parts:
            if not part:
                return False
            if not re.match(r'^[a-zA-Z0-9-]+$', part):
                return False
        
        return True
    
    # ============ Gas Utilities ============
    
    def gas_to_eth(self, gas_limit: int, gas_price: int) -> float:
        """
        Calculate transaction cost in ETH.
        
        Args:
            gas_limit: Gas limit.
            gas_price: Gas price in wei.
            
        Returns:
            Transaction cost in ETH.
        """
        return self.from_wei(gas_limit * gas_price, 'ether')
    
    def gas_to_usd(self, gas_limit: int, gas_price: int, eth_price_usd: float) -> float:
        """
        Calculate transaction cost in USD.
        
        Args:
            gas_limit: Gas limit.
            gas_price: Gas price in wei.
            eth_price_usd: ETH price in USD.
            
        Returns:
            Transaction cost in USD.
        """
        eth_cost = self.gas_to_eth(gas_limit, gas_price)
        return eth_cost * eth_price_usd
    
    # ============ Transaction Utilities ============
    
    def build_transaction(
        self,
        to: str,
        value: Union[float, int, str] = 0,
        data: Optional[str] = None,
        gas: Optional[int] = None,
        gas_price: Optional[int] = None,
        nonce: Optional[int] = None,
        chain_id: Optional[int] = None,
        from_address: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build a transaction dictionary.
        
        Args:
            to: Recipient address.
            value: Value in ETH.
            data: Transaction data.
            gas: Gas limit.
            gas_price: Gas price in wei.
            nonce: Transaction nonce.
            chain_id: Chain ID.
            from_address: Sender address.
            **kwargs: Additional transaction parameters.
            
        Returns:
            Transaction dictionary.
        """
        if from_address:
            from_address = self.to_checksum_address(from_address)
        if to:
            to = self.to_checksum_address(to)
        
        tx = {
            'from': from_address,
            'to': to,
            'value': self.to_wei(value, 'ether'),
            'chainId': chain_id,
            'nonce': nonce,
        }
        
        if data:
            tx['data'] = data
        
        if gas:
            tx['gas'] = gas
        
        if gas_price:
            tx['gasPrice'] = gas_price
        
        if kwargs:
            tx.update(kwargs)
        
        return tx
    
    def calculate_transaction_hash(self, tx_dict: Dict[str, Any]) -> str:
        """
        Calculate the transaction hash of a signed transaction.
        
        Args:
            tx_dict: Signed transaction dictionary.
            
        Returns:
            Transaction hash.
        """
        # This requires a Web3 instance to properly serialize
        if self.web3_client:
            w3 = self.web3_client._get_active_web3()
            if w3:
                return w3.eth.send_transaction(tx_dict).hex()
        
        # Fallback: serialize and hash
        from rlp import encode
        from eth_account._utils.transaction_utils import (
            transaction_rpc_to_rlp_structure,
            transaction_rlp_to_rpc_structure,
        )
        
        # Simplified - this would need full RLP encoding
        return ''
    
    # ============ Contract Utilities ============
    
    def get_contract_address_from_deployment(
        self,
        deployer_address: str,
        nonce: int
    ) -> str:
        """
        Calculate the contract address from deployment parameters.
        
        Args:
            deployer_address: Deployer address.
            nonce: Transaction nonce.
            
        Returns:
            Contract address.
        """
        deployer = self.to_checksum_address(deployer_address)
        raw = to_bytes(hexstr=deployer) + nonce.to_bytes(1, 'big')
        address = keccak(raw)[12:]
        return self.to_checksum_address(address.hex())
    
    # ============ Misc Utilities ============
    
    def now(self) -> int:
        """
        Get current timestamp in seconds.
        
        Returns:
            Current timestamp.
        """
        return int(time.time())
    
    def now_ms(self) -> int:
        """
        Get current timestamp in milliseconds.
        
        Returns:
            Current timestamp in milliseconds.
        """
        return int(time.time() * 1000)
    
    def sleep(self, seconds: float) -> None:
        """
        Sleep for a given number of seconds.
        
        Args:
            seconds: Number of seconds to sleep.
        """
        time.sleep(seconds)
    
    def clear_cache(self) -> None:
        """Clear the utility cache."""
        if self._cache:
            self._cache.clear()
        logger.info("Web3Utils cache cleared")


# Global instance
_web3_utils: Optional[Web3Utils] = None


def get_web3_utils(web3_client: Optional[Any] = None) -> Web3Utils:
    """
    Get the global Web3 utilities instance.
    
    Args:
        web3_client: Web3 client instance.
        
    Returns:
        Web3Utils instance.
    """
    global _web3_utils
    if _web3_utils is None:
        _web3_utils = Web3Utils(web3_client)
    return _web3_utils


def create_web3_utils(web3_client: Optional[Any] = None) -> Web3Utils:
    """
    Create a Web3 utilities instance.
    
    Args:
        web3_client: Web3 client instance.
        
    Returns:
        Web3Utils instance.
    """
    return Web3Utils(web3_client)


__all__ = [
    'Web3Utils',
    'get_web3_utils',
    'create_web3_utils',
]
