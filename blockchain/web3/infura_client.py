"""
Infura Client Module
======================

This module provides a client for interacting with the Infura API.
It uses web3.py to connect to Ethereum nodes via Infura's infrastructure.
Supports both HTTP and WebSocket connections for real-time data.
"""

import json
import time
from typing import Dict, List, Optional, Union, Any, Tuple
from decimal import Decimal
from pathlib import Path
from datetime import datetime

from web3 import Web3
from web3.middleware import geth_poa_middleware, http_retry_request_middleware
from web3.types import TxParams, Wei, HexBytes, BlockData, LogReceipt
from eth_account import Account
from eth_account.signers.local import LocalAccount
from hexbytes import HexBytes

from trading.bots.swing_bot.utils.converters import to_int, to_float, to_str
from trading.bots.swing_bot.utils.validators import validate_data


class InfuraClient:
    """
    Client for Infura API using web3.py.
    
    Provides methods to interact with Ethereum blockchain via Infura.
    Supports mainnet and testnets (Goerli, Sepolia, etc.).
    """
    
    SUPPORTED_NETWORKS = {
        'mainnet': 'mainnet.infura.io/v3/',
        'goerli': 'goerli.infura.io/v3/',
        'sepolia': 'sepolia.infura.io/v3/',
        'polygon': 'polygon-mainnet.infura.io/v3/',
        'polygon_mumbai': 'polygon-mumbai.infura.io/v3/',
        'arbitrum': 'arbitrum-mainnet.infura.io/v3/',
        'optimism': 'optimism-mainnet.infura.io/v3/',
    }
    
    def __init__(
        self,
        project_id: str,
        network: str = 'mainnet',
        api_secret: Optional[str] = None,
        use_websocket: bool = False,
        request_timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize the Infura client.
        
        Args:
            project_id: Infura project ID
            network: Network name ('mainnet', 'goerli', 'sepolia', 'polygon', etc.)
            api_secret: Optional API secret for authenticated endpoints
            use_websocket: Use WebSocket instead of HTTP
            request_timeout: Timeout in seconds for requests
            max_retries: Maximum number of retries
        """
        self.project_id = project_id
        self.network = network
        self.api_secret = api_secret
        self.use_websocket = use_websocket
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        
        # Build endpoint URL
        if network not in self.SUPPORTED_NETWORKS:
            raise ValueError(f"Unsupported network: {network}")
        
        base = self.SUPPORTED_NETWORKS[network]
        if api_secret:
            endpoint = f"https://{base}{project_id}"
            self.ws_endpoint = f"wss://{base.replace('mainnet', 'mainnet').replace('goerli', 'goerli').replace('sepolia', 'sepolia')}{project_id}"
        else:
            endpoint = f"https://{base}{project_id}"
            self.ws_endpoint = f"wss://{base.replace('mainnet', 'mainnet').replace('goerli', 'goerli').replace('sepolia', 'sepolia')}{project_id}"
        
        # Initialize Web3
        if use_websocket:
            self.w3 = Web3(Web3.WebsocketProvider(
                self.ws_endpoint,
                websocket_timeout=request_timeout,
                websocket_kwargs={'max_size': 2**26}
            ))
        else:
            self.w3 = Web3(Web3.HTTPProvider(
                endpoint,
                request_kwargs={'timeout': request_timeout}
            ))
        
        # Inject middleware
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        if max_retries > 1:
            self.w3.middleware_onion.add(http_retry_request_middleware)
        
        # Check connection
        if not self.is_connected():
            raise ConnectionError("Failed to connect to Infura")
        
        # Store account (will be set when private key is provided)
        self._account: Optional[LocalAccount] = None
    
    def is_connected(self) -> bool:
        """
        Check if the client is connected to the node.
        
        Returns:
            True if connected, False otherwise
        """
        return self.w3.is_connected()
    
    def set_private_key(self, private_key: str) -> None:
        """
        Set the private key for signing transactions.
        
        Args:
            private_key: Private key in hex format (with or without 0x prefix)
        """
        self._account = Account.from_key(private_key)
    
    @property
    def address(self) -> Optional[str]:
        """Get the address associated with the private key."""
        if self._account:
            return self._account.address
        return None
    
    @property
    def chain_id(self) -> int:
        """Get the chain ID of the connected network."""
        return self.w3.eth.chain_id
    
    # ============ Account Methods ============
    
    def get_balance(self, address: Optional[str] = None) -> float:
        """
        Get the ETH balance for an address.
        
        Args:
            address: Ethereum address (defaults to the account address)
            
        Returns:
            Balance in ETH as float
        """
        if address is None:
            if not self._account:
                raise ValueError("No address provided and no private key set")
            address = self._account.address
        
        wei = self.w3.eth.get_balance(address)
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
            token_address: Token contract address
            address: Wallet address (defaults to account address)
            decimals: Token decimals (if None, will be fetched from contract)
            
        Returns:
            Token balance in token units
        """
        if address is None:
            if not self._account:
                raise ValueError("No address provided and no private key set")
            address = self._account.address
        
        # Fetch decimals if not provided
        if decimals is None:
            decimals = self.call_contract_function(token_address, 'decimals') or 18
        
        balance = self.call_contract_function(
            token_address,
            'balanceOf',
            address
        )
        
        if balance is None:
            return 0.0
        
        return balance / (10 ** decimals)
    
    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """
        Get ERC-20 token information.
        
        Args:
            token_address: Token contract address
            
        Returns:
            Dictionary with name, symbol, decimals, totalSupply
        """
        info = {}
        
        # Name
        try:
            info['name'] = self.call_contract_function(token_address, 'name')
        except:
            info['name'] = 'Unknown'
        
        # Symbol
        try:
            info['symbol'] = self.call_contract_function(token_address, 'symbol')
        except:
            info['symbol'] = 'Unknown'
        
        # Decimals
        try:
            info['decimals'] = self.call_contract_function(token_address, 'decimals') or 18
        except:
            info['decimals'] = 18
        
        # Total supply
        try:
            total = self.call_contract_function(token_address, 'totalSupply')
            info['total_supply'] = total / (10 ** info['decimals']) if total else 0
        except:
            info['total_supply'] = 0
        
        return info
    
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
            to: Recipient address
            value: Amount in ETH (float)
            data: Transaction data (hex string)
            gas: Gas limit (auto-estimated if None)
            gas_price: Gas price in wei (legacy)
            nonce: Transaction nonce (auto-fetched if None)
            max_fee_per_gas: Max fee per gas for EIP-1559
            max_priority_fee_per_gas: Max priority fee for EIP-1559
            from_address: Sender address (defaults to account address)
            
        Returns:
            Transaction hash as hex string
        """
        if not self._account:
            raise ValueError("Private key not set")
        
        if from_address is None:
            from_address = self._account.address
        
        # Build transaction dict
        tx: TxParams = {
            'from': from_address,
            'to': to,
            'value': Web3.to_wei(value, 'ether'),
            'nonce': nonce if nonce is not None else self.w3.eth.get_transaction_count(from_address),
        }
        
        # Add data if provided
        if data:
            tx['data'] = data
        
        # EIP-1559 or legacy
        if max_fee_per_gas is not None and max_priority_fee_per_gas is not None:
            tx['maxFeePerGas'] = max_fee_per_gas
            tx['maxPriorityFeePerGas'] = max_priority_fee_per_gas
            tx['type'] = '0x2'
        elif gas_price is not None:
            tx['gasPrice'] = gas_price
        else:
            # Auto-detect: use EIP-1559 if supported
            if self.w3.eth.max_priority_fee is not None:
                base_fee = self.w3.eth.get_block('pending')['baseFeePerGas'] or 0
                max_priority = self.w3.eth.max_priority_fee
                tx['maxFeePerGas'] = base_fee + max_priority * 2
                tx['maxPriorityFeePerGas'] = max_priority
                tx['type'] = '0x2'
            else:
                tx['gasPrice'] = self.w3.eth.gas_price
        
        # Gas limit
        if gas is None:
            tx['gas'] = self.w3.eth.estimate_gas(tx)
        else:
            tx['gas'] = gas
        
        # Sign and send
        signed = self._account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
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
            token_address: Token contract address
            to: Recipient address
            amount: Amount in token units (float)
            decimals: Token decimals (auto-fetched if None)
            gas: Gas limit
            gas_price: Gas price in wei
            nonce: Transaction nonce
            max_fee_per_gas: Max fee per gas for EIP-1559
            max_priority_fee_per_gas: Max priority fee
            from_address: Sender address (defaults to account address)
            
        Returns:
            Transaction hash as hex string
        """
        if not self._account:
            raise ValueError("Private key not set")
        
        if from_address is None:
            from_address = self._account.address
        
        # Fetch decimals if not provided
        if decimals is None:
            decimals = self.call_contract_function(token_address, 'decimals') or 18
        
        # Convert amount to wei
        amount_wei = int(Decimal(str(amount)) * (10 ** decimals))
        
        # Prepare transfer function call
        data = self._encode_function_call(
            token_address,
            'transfer',
            to,
            amount_wei
        )
        
        # Send transaction
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
            tx_hash: Transaction hash
            
        Returns:
            Transaction receipt as dict
        """
        receipt = self.w3.eth.get_transaction_receipt(tx_hash)
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
            'logs': [{'address': log['address'], 'data': log['data'].hex(), 'topics': [t.hex() for t in log['topics']]} for log in receipt['logs']]
        }
    
    def wait_for_transaction_receipt(self, tx_hash: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Wait for a transaction receipt.
        
        Args:
            tx_hash: Transaction hash
            timeout: Maximum time to wait in seconds
            
        Returns:
            Transaction receipt as dict
        """
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
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
            'logs': [{'address': log['address'], 'data': log['data'].hex(), 'topics': [t.hex() for t in log['topics']]} for log in receipt['logs']]
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
            contract_address: Contract address
            function_name: Function name
            *args: Function arguments
            abi: Contract ABI (optional)
            
        Returns:
            Function return value
        """
        if abi is None:
            # Try to get ABI from cache or use minimal ERC-20 ABI
            abi = self._get_contract_abi(contract_address)
        
        contract = self.w3.eth.contract(address=contract_address, abi=abi)
        function = getattr(contract.functions, function_name)
        result = function(*args).call()
        return result
    
    def _encode_function_call(
        self,
        contract_address: str,
        function_name: str,
        *args,
        abi: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Encode a contract function call for a transaction.
        
        Args:
            contract_address: Contract address
            function_name: Function name
            *args: Function arguments
            abi: Contract ABI (optional)
            
        Returns:
            Hex-encoded transaction data
        """
        if abi is None:
            abi = self._get_contract_abi(contract_address)
        
        contract = self.w3.eth.contract(address=contract_address, abi=abi)
        function = getattr(contract.functions, function_name)
        return function(*args).build_transaction({'from': self.address})['data'].hex()
    
    def _get_contract_abi(self, contract_address: str) -> List[Dict[str, Any]]:
        """
        Get contract ABI (from cache or default ERC-20).
        
        Args:
            contract_address: Contract address
            
        Returns:
            ABI as list of dictionaries
        """
        # Placeholder: In production, fetch from Etherscan or use a cache
        # For now, return a minimal ERC-20 ABI
        return [
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "success", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "success", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"name": "remaining", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_from", "type": "address"},
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transferFrom",
                "outputs": [{"name": "success", "type": "bool"}],
                "type": "function"
            }
        ]
    
    # ============ Block Methods ============
    
    def get_block(self, block_identifier: Union[int, str] = 'latest') -> Dict[str, Any]:
        """
        Get block information.
        
        Args:
            block_identifier: Block number, 'latest', 'pending', or 'earliest'
            
        Returns:
            Block data as dictionary
        """
        block = self.w3.eth.get_block(block_identifier)
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
        """
        Get the current block number.
        
        Returns:
            Current block number
        """
        return self.w3.eth.block_number
    
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
            from_block: Starting block
            to_block: Ending block
            address: Contract address
            topics: List of topics to filter
            
        Returns:
            List of log entries
        """
        logs = self.w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': address,
            'topics': topics
        })
        
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
        """
        Get current gas price in wei.
        
        Returns:
            Gas price in wei
        """
        return self.w3.eth.gas_price
    
    def get_gas_price_gwei(self) -> float:
        """
        Get current gas price in Gwei.
        
        Returns:
            Gas price in Gwei
        """
        return self.w3.eth.gas_price / 1e9
    
    def get_max_priority_fee(self) -> int:
        """
        Get current max priority fee (tip).
        
        Returns:
            Max priority fee in wei
        """
        return self.w3.eth.max_priority_fee
    
    def estimate_gas(self, tx: Dict[str, Any]) -> int:
        """
        Estimate gas for a transaction.
        
        Args:
            tx: Transaction dictionary
            
        Returns:
            Estimated gas
        """
        return self.w3.eth.estimate_gas(tx)
    
    # ============ ENS Methods ============
    
    def resolve_ens(self, name: str) -> Optional[str]:
        """
        Resolve an ENS name to an address.
        
        Args:
            name: ENS name (e.g., 'vitalik.eth')
            
        Returns:
            Address or None if not found
        """
        return self.w3.ens.address(name)
    
    def reverse_resolve_ens(self, address: str) -> Optional[str]:
        """
        Resolve an address to an ENS name.
        
        Args:
            address: Ethereum address
            
        Returns:
            ENS name or None if not found
        """
        return self.w3.ens.name(address)
    
    # ============ Utility Methods ============
    
    def to_checksum_address(self, address: str) -> str:
        """
        Convert an address to checksum format.
        
        Args:
            address: Ethereum address
            
        Returns:
            Checksummed address
        """
        return Web3.to_checksum_address(address)
    
    def is_address(self, address: str) -> bool:
        """
        Check if a string is a valid Ethereum address.
        
        Args:
            address: String to check
            
        Returns:
            True if valid address, False otherwise
        """
        return Web3.is_address(address)
    
    def is_checksum_address(self, address: str) -> bool:
        """
        Check if an address is checksummed.
        
        Args:
            address: Address to check
            
        Returns:
            True if checksummed, False otherwise
        """
        return Web3.is_checksum_address(address)
    
    def to_wei(self, amount: Union[float, int, str], unit: str = 'ether') -> int:
        """
        Convert an amount to wei.
        
        Args:
            amount: Amount
            unit: Unit ('ether', 'gwei', 'wei', etc.)
            
        Returns:
            Amount in wei
        """
        return self.w3.to_wei(amount, unit)
    
    def from_wei(self, amount: int, unit: str = 'ether') -> float:
        """
        Convert wei to another unit.
        
        Args:
            amount: Amount in wei
            unit: Target unit
            
        Returns:
            Amount in target unit
        """
        return self.w3.from_wei(amount, unit)
    
    def close(self) -> None:
        """Close the Web3 connection (for WebSocket)."""
        if self.w3.provider and hasattr(self.w3.provider, 'close'):
            self.w3.provider.close()


def create_infura_client(config: Dict[str, Any]) -> InfuraClient:
    """
    Create an Infura client from configuration.
    
    Args:
        config: Configuration with 'project_id', optional 'network', 'api_secret', etc.
        
    Returns:
        InfuraClient instance
    """
    return InfuraClient(
        project_id=config.get('project_id', ''),
        network=config.get('network', 'mainnet'),
        api_secret=config.get('api_secret'),
        use_websocket=config.get('use_websocket', False),
        request_timeout=config.get('request_timeout', 30),
        max_retries=config.get('max_retries', 3),
    )


__all__ = [
    'InfuraClient',
    'create_infura_client'
]
