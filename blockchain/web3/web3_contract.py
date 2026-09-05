"""
Web3 Contract Module
======================

This module provides contract interaction capabilities for the Web3 client.
It supports ERC20, ERC721, ERC1155 tokens and custom contract interactions.
"""

import json
import time
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from pathlib import Path

from web3 import Web3
from web3.types import TxParams, Wei, HexBytes, LogReceipt
from eth_account.signers.local import LocalAccount
from hexbytes import HexBytes

from trading.bots.swing_bot.utils.converters import to_int, to_float, to_str
from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.helpers import load_json, load_yaml

logger = logging.getLogger(__name__)


@dataclass
class ContractEvent:
    """Contract event data structure."""
    name: str
    address: str
    block_number: int
    transaction_hash: str
    log_index: int
    args: Dict[str, Any]
    timestamp: Optional[datetime] = None


@dataclass
class ContractCall:
    """Contract call data structure."""
    contract_address: str
    function_name: str
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    timestamp: datetime
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ContractTransaction:
    """Contract transaction data structure."""
    contract_address: str
    function_name: str
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    tx_hash: str
    from_address: str
    timestamp: datetime
    receipt: Optional[Dict[str, Any]] = None
    status: str = 'pending'  # pending, mined, failed


class Web3Contract:
    """
    Web3 contract wrapper for interacting with smart contracts.
    
    Provides methods for contract calls, transactions, and event handling.
    Supports ERC20, ERC721, ERC1155, and custom contracts.
    """
    
    # Standard ABIs
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
        {"anonymous": False, "inputs": [{"indexed": True, "name": "from", "type": "address"}, {"indexed": True, "name": "to", "type": "address"}, {"indexed": False, "name": "value", "type": "uint256"}], "name": "Transfer", "type": "event"},
        {"anonymous": False, "inputs": [{"indexed": True, "name": "owner", "type": "address"}, {"indexed": True, "name": "spender", "type": "address"}, {"indexed": False, "name": "value", "type": "uint256"}], "name": "Approval", "type": "event"},
    ]
    
    ERC721_ABI = [
        {"constant": True, "inputs": [{"name": "tokenId", "type": "uint256"}], "name": "ownerOf", "outputs": [{"name": "", "type": "address"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
        {"constant": False, "inputs": [{"name": "from", "type": "address"}, {"name": "to", "type": "address"}, {"name": "tokenId", "type": "uint256"}], "name": "transferFrom", "outputs": [], "type": "function"},
        {"constant": False, "inputs": [{"name": "to", "type": "address"}, {"name": "tokenId", "type": "uint256"}], "name": "approve", "outputs": [], "type": "function"},
        {"constant": True, "inputs": [{"name": "tokenId", "type": "uint256"}], "name": "getApproved", "outputs": [{"name": "", "type": "address"}], "type": "function"},
        {"constant": False, "inputs": [{"name": "to", "type": "address"}, {"name": "tokenId", "type": "uint256"}], "name": "safeTransferFrom", "outputs": [], "type": "function"},
        {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "tokenId", "type": "uint256"}], "name": "tokenURI", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"anonymous": False, "inputs": [{"indexed": True, "name": "from", "type": "address"}, {"indexed": True, "name": "to", "type": "address"}, {"indexed": True, "name": "tokenId", "type": "uint256"}], "name": "Transfer", "type": "event"},
        {"anonymous": False, "inputs": [{"indexed": True, "name": "owner", "type": "address"}, {"indexed": True, "name": "approved", "type": "address"}, {"indexed": True, "name": "tokenId", "type": "uint256"}], "name": "Approval", "type": "event"},
    ]
    
    ERC1155_ABI = [
        {"constant": True, "inputs": [{"name": "account", "type": "address"}, {"name": "id", "type": "uint256"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "accounts", "type": "address[]"}, {"name": "ids", "type": "uint256[]"}], "name": "balanceOfBatch", "outputs": [{"name": "", "type": "uint256[]"}], "type": "function"},
        {"constant": False, "inputs": [{"name": "from", "type": "address"}, {"name": "to", "type": "address"}, {"name": "id", "type": "uint256"}, {"name": "amount", "type": "uint256"}, {"name": "data", "type": "bytes"}], "name": "safeTransferFrom", "outputs": [], "type": "function"},
        {"constant": False, "inputs": [{"name": "from", "type": "address"}, {"name": "to", "type": "address"}, {"name": "ids", "type": "uint256[]"}, {"name": "amounts", "type": "uint256[]"}, {"name": "data", "type": "bytes"}], "name": "safeBatchTransferFrom", "outputs": [], "type": "function"},
        {"constant": True, "inputs": [{"name": "id", "type": "uint256"}], "name": "uri", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"anonymous": False, "inputs": [{"indexed": True, "name": "operator", "type": "address"}, {"indexed": True, "name": "from", "type": "address"}, {"indexed": True, "name": "to", "type": "address"}, {"indexed": False, "name": "ids", "type": "uint256[]"}, {"indexed": False, "name": "values", "type": "uint256[]"}], "name": "TransferBatch", "type": "event"},
        {"anonymous": False, "inputs": [{"indexed": True, "name": "operator", "type": "address"}, {"indexed": True, "name": "from", "type": "address"}, {"indexed": True, "name": "to", "type": "address"}, {"indexed": False, "name": "id", "type": "uint256"}, {"indexed": False, "name": "value", "type": "uint256"}], "name": "TransferSingle", "type": "event"},
    ]
    
    def __init__(
        self,
        address: str,
        abi: Optional[List[Dict[str, Any]]] = None,
        web3_client: Optional[Any] = None,
        contract_type: str = 'custom'
    ):
        """
        Initialize the contract wrapper.
        
        Args:
            address: Contract address.
            abi: Contract ABI (uses standard ABI if None).
            web3_client: Web3 client instance.
            contract_type: Type of contract ('erc20', 'erc721', 'erc1155', 'custom').
        """
        self.address = Web3.to_checksum_address(address)
        self.contract_type = contract_type
        self.web3_client = web3_client
        self._abi = abi
        self._contract = None
        
        # Set default ABI based on contract type
        if abi is None:
            if contract_type == 'erc20':
                self._abi = self.ERC20_ABI
            elif contract_type == 'erc721':
                self._abi = self.ERC721_ABI
            elif contract_type == 'erc1155':
                self._abi = self.ERC1155_ABI
        
        # Initialize contract
        self._init_contract()
    
    def _init_contract(self) -> None:
        """Initialize the Web3 contract instance."""
        if self.web3_client is None:
            raise ValueError("Web3 client not set")
        
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        self._contract = w3.eth.contract(
            address=self.address,
            abi=self._abi
        )
    
    def set_web3_client(self, web3_client: Any) -> None:
        """
        Set the Web3 client.
        
        Args:
            web3_client: Web3 client instance.
        """
        self.web3_client = web3_client
        self._init_contract()
    
    # ============ Read Methods ============
    
    def call(
        self,
        function_name: str,
        *args,
        from_address: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Call a read-only contract function.
        
        Args:
            function_name: Function name.
            *args: Function arguments.
            from_address: Caller address.
            **kwargs: Additional keyword arguments.
            
        Returns:
            Function return value.
        """
        if self._contract is None:
            raise ValueError("Contract not initialized")
        
        function = getattr(self._contract.functions, function_name)
        call_params = {}
        if from_address:
            call_params['from'] = from_address
        
        return function(*args).call(call_params)
    
    def balance_of(self, address: str) -> float:
        """
        Get the balance of an address (ERC20/ERC721/ERC1155).
        
        Args:
            address: Wallet address.
            
        Returns:
            Balance in token units.
        """
        if self.contract_type == 'erc20':
            decimals = self.call('decimals') or 18
            balance = self.call('balanceOf', address)
            return balance / (10 ** decimals) if balance else 0.0
        elif self.contract_type == 'erc721':
            return self.call('balanceOf', address)
        elif self.contract_type == 'erc1155':
            # For ERC1155, need token ID
            return 0.0
        else:
            raise ValueError(f"balance_of not supported for {self.contract_type}")
    
    def balance_of_token_id(self, address: str, token_id: int) -> float:
        """
        Get the balance of a specific token ID for ERC1155.
        
        Args:
            address: Wallet address.
            token_id: Token ID.
            
        Returns:
            Balance in token units.
        """
        if self.contract_type != 'erc1155':
            raise ValueError(f"balance_of_token_id only supported for ERC1155")
        
        balance = self.call('balanceOf', address, token_id)
        return balance or 0.0
    
    def total_supply(self) -> float:
        """
        Get the total supply (ERC20 only).
        
        Returns:
            Total supply in token units.
        """
        if self.contract_type != 'erc20':
            raise ValueError(f"total_supply only supported for ERC20")
        
        decimals = self.call('decimals') or 18
        total = self.call('totalSupply')
        return total / (10 ** decimals) if total else 0.0
    
    def allowance(self, owner: str, spender: str) -> float:
        """
        Get the allowance (ERC20 only).
        
        Args:
            owner: Token owner.
            spender: Token spender.
            
        Returns:
            Allowance amount in token units.
        """
        if self.contract_type != 'erc20':
            raise ValueError(f"allowance only supported for ERC20")
        
        decimals = self.call('decimals') or 18
        allowance = self.call('allowance', owner, spender)
        return allowance / (10 ** decimals) if allowance else 0.0
    
    def owner_of(self, token_id: int) -> str:
        """
        Get the owner of an NFT (ERC721 only).
        
        Args:
            token_id: Token ID.
            
        Returns:
            Owner address.
        """
        if self.contract_type != 'erc721':
            raise ValueError(f"owner_of only supported for ERC721")
        
        return self.call('ownerOf', token_id)
    
    def token_uri(self, token_id: int) -> str:
        """
        Get the token URI (ERC721/ERC1155).
        
        Args:
            token_id: Token ID.
            
        Returns:
            Token URI.
        """
        if self.contract_type in ['erc721', 'erc1155']:
            return self.call('uri', token_id)
        else:
            raise ValueError(f"token_uri not supported for {self.contract_type}")
    
    def token_info(self) -> Dict[str, Any]:
        """
        Get token information.
        
        Returns:
            Dictionary with name, symbol, decimals.
        """
        info = {}
        
        if self.contract_type == 'erc20':
            try:
                info['name'] = self.call('name')
            except:
                info['name'] = 'Unknown'
            try:
                info['symbol'] = self.call('symbol')
            except:
                info['symbol'] = 'Unknown'
            try:
                info['decimals'] = self.call('decimals') or 18
            except:
                info['decimals'] = 18
        elif self.contract_type == 'erc721':
            try:
                info['name'] = self.call('name')
            except:
                info['name'] = 'Unknown'
            try:
                info['symbol'] = self.call('symbol')
            except:
                info['symbol'] = 'Unknown'
        else:
            info['name'] = 'Unknown'
            info['symbol'] = 'Unknown'
        
        info['address'] = self.address
        info['type'] = self.contract_type
        
        return info
    
    # ============ Write Methods ============
    
    def send_transaction(
        self,
        function_name: str,
        *args,
        from_address: Optional[str] = None,
        gas: Optional[int] = None,
        gas_price: Optional[int] = None,
        nonce: Optional[int] = None,
        max_fee_per_gas: Optional[int] = None,
        max_priority_fee_per_gas: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Send a contract transaction.
        
        Args:
            function_name: Function name.
            *args: Function arguments.
            from_address: Sender address.
            gas: Gas limit.
            gas_price: Gas price in wei.
            nonce: Transaction nonce.
            max_fee_per_gas: Max fee per gas for EIP-1559.
            max_priority_fee_per_gas: Max priority fee.
            **kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        if self._contract is None:
            raise ValueError("Contract not initialized")
        
        if self.web3_client is None:
            raise ValueError("Web3 client not set")
        
        if from_address is None:
            if self.web3_client._account:
                from_address = self.web3_client._account.address
            else:
                raise ValueError("No from address provided and no account set")
        
        function = getattr(self._contract.functions, function_name)
        tx = function(*args).build_transaction({
            'from': from_address,
            'gas': gas,
            'gasPrice': gas_price,
            'nonce': nonce,
            'maxFeePerGas': max_fee_per_gas,
            'maxPriorityFeePerGas': max_priority_fee_per_gas,
            **kwargs
        })
        
        return self.web3_client.send_transaction(
            to=self.address,
            value=tx.get('value', 0),
            data=tx.get('data', ''),
            gas=gas,
            gas_price=gas_price,
            nonce=nonce,
            max_fee_per_gas=max_fee_per_gas,
            max_priority_fee_per_gas=max_priority_fee_per_gas,
            from_address=from_address
        )
    
    def transfer(
        self,
        to: str,
        amount: Union[float, int, str],
        from_address: Optional[str] = None,
        decimals: Optional[int] = None,
        **tx_kwargs
    ) -> str:
        """
        Transfer tokens (ERC20 only).
        
        Args:
            to: Recipient address.
            amount: Amount in token units.
            from_address: Sender address.
            decimals: Token decimals (auto-fetched if None).
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        if self.contract_type != 'erc20':
            raise ValueError(f"transfer only supported for ERC20")
        
        if decimals is None:
            decimals = self.call('decimals') or 18
        
        amount_wei = int(Decimal(str(amount)) * (10 ** decimals))
        
        return self.send_transaction(
            'transfer',
            to,
            amount_wei,
            from_address=from_address,
            **tx_kwargs
        )
    
    def transfer_from(
        self,
        from_address: str,
        to: str,
        amount: Union[float, int, str],
        decimals: Optional[int] = None,
        **tx_kwargs
    ) -> str:
        """
        Transfer from another address (ERC20 only).
        
        Args:
            from_address: Sender address.
            to: Recipient address.
            amount: Amount in token units.
            decimals: Token decimals (auto-fetched if None).
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        if self.contract_type != 'erc20':
            raise ValueError(f"transfer_from only supported for ERC20")
        
        if decimals is None:
            decimals = self.call('decimals') or 18
        
        amount_wei = int(Decimal(str(amount)) * (10 ** decimals))
        
        return self.send_transaction(
            'transferFrom',
            from_address,
            to,
            amount_wei,
            from_address=from_address,
            **tx_kwargs
        )
    
    def approve(
        self,
        spender: str,
        amount: Union[float, int, str],
        decimals: Optional[int] = None,
        **tx_kwargs
    ) -> str:
        """
        Approve spending (ERC20 only).
        
        Args:
            spender: Spender address.
            amount: Amount in token units.
            decimals: Token decimals (auto-fetched if None).
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        if self.contract_type != 'erc20':
            raise ValueError(f"approve only supported for ERC20")
        
        if decimals is None:
            decimals = self.call('decimals') or 18
        
        amount_wei = int(Decimal(str(amount)) * (10 ** decimals))
        
        return self.send_transaction(
            'approve',
            spender,
            amount_wei,
            **tx_kwargs
        )
    
    def transfer_nft(
        self,
        to: str,
        token_id: int,
        from_address: Optional[str] = None,
        **tx_kwargs
    ) -> str:
        """
        Transfer an NFT (ERC721 only).
        
        Args:
            to: Recipient address.
            token_id: Token ID.
            from_address: Sender address.
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        if self.contract_type != 'erc721':
            raise ValueError(f"transfer_nft only supported for ERC721")
        
        if from_address is None:
            from_address = self.web3_client.address
        
        return self.send_transaction(
            'transferFrom',
            from_address,
            to,
            token_id,
            from_address=from_address,
            **tx_kwargs
        )
    
    def safe_transfer_nft(
        self,
        to: str,
        token_id: int,
        from_address: Optional[str] = None,
        **tx_kwargs
    ) -> str:
        """
        Safely transfer an NFT (ERC721 only).
        
        Args:
            to: Recipient address.
            token_id: Token ID.
            from_address: Sender address.
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        if self.contract_type != 'erc721':
            raise ValueError(f"safe_transfer_nft only supported for ERC721")
        
        if from_address is None:
            from_address = self.web3_client.address
        
        return self.send_transaction(
            'safeTransferFrom',
            from_address,
            to,
            token_id,
            from_address=from_address,
            **tx_kwargs
        )
    
    # ============ Event Methods ============
    
    def get_events(
        self,
        event_name: str,
        from_block: Union[int, str] = 'earliest',
        to_block: Union[int, str] = 'latest',
        argument_filters: Optional[Dict[str, Any]] = None
    ) -> List[ContractEvent]:
        """
        Get contract events.
        
        Args:
            event_name: Event name.
            from_block: Starting block.
            to_block: Ending block.
            argument_filters: Filters for event arguments.
            
        Returns:
            List of ContractEvent objects.
        """
        if self._contract is None:
            raise ValueError("Contract not initialized")
        
        event = getattr(self._contract.events, event_name)
        entries = event.get_logs(
            fromBlock=from_block,
            toBlock=to_block,
            argument_filters=argument_filters or {}
        )
        
        result = []
        for entry in entries:
            result.append(ContractEvent(
                name=event_name,
                address=entry['address'],
                block_number=entry['blockNumber'],
                transaction_hash=entry['transactionHash'].hex(),
                log_index=entry['logIndex'],
                args=entry['args']
            ))
        
        return result
    
    def get_transfer_events(
        self,
        from_block: Union[int, str] = 'earliest',
        to_block: Union[int, str] = 'latest',
        address_filter: Optional[str] = None
    ) -> List[ContractEvent]:
        """
        Get Transfer events.
        
        Args:
            from_block: Starting block.
            to_block: Ending block.
            address_filter: Filter by address (from or to).
            
        Returns:
            List of Transfer events.
        """
        argument_filters = {}
        if address_filter:
            argument_filters = {'from': address_filter}
        
        return self.get_events('Transfer', from_block, to_block, argument_filters)
    
    # ============ Transaction Management ============
    
    def wait_for_transaction(self, tx_hash: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Wait for a transaction to be mined.
        
        Args:
            tx_hash: Transaction hash.
            timeout: Maximum time to wait in seconds.
            
        Returns:
            Transaction receipt.
        """
        if self.web3_client is None:
            raise ValueError("Web3 client not set")
        
        return self.web3_client.wait_for_transaction_receipt(tx_hash, timeout)
    
    # ============ Utility Methods ============
    
    def get_contract_info(self) -> Dict[str, Any]:
        """
        Get contract information.
        
        Returns:
            Contract information dictionary.
        """
        info = {
            'address': self.address,
            'type': self.contract_type,
            'functions': [],
            'events': []
        }
        
        if self._abi:
            for item in self._abi:
                if item.get('type') == 'function':
                    info['functions'].append({
                        'name': item.get('name'),
                        'inputs': item.get('inputs', []),
                        'outputs': item.get('outputs', []),
                        'stateMutability': item.get('stateMutability', '')
                    })
                elif item.get('type') == 'event':
                    info['events'].append({
                        'name': item.get('name'),
                        'inputs': item.get('inputs', []),
                        'anonymous': item.get('anonymous', False)
                    })
        
        return info
    
    def encode_function_call(
        self,
        function_name: str,
        *args,
        **kwargs
    ) -> str:
        """
        Encode a function call without sending it.
        
        Args:
            function_name: Function name.
            *args: Function arguments.
            **kwargs: Additional parameters.
            
        Returns:
            Hex-encoded transaction data.
        """
        if self._contract is None:
            raise ValueError("Contract not initialized")
        
        function = getattr(self._contract.functions, function_name)
        return function(*args).build_transaction(kwargs)['data'].hex()
    
    def decode_function_input(self, data: str) -> Dict[str, Any]:
        """
        Decode function input data.
        
        Args:
            data: Hex-encoded transaction data.
            
        Returns:
            Decoded function call information.
        """
        if self._contract is None:
            raise ValueError("Contract not initialized")
        
        return self._contract.decode_function_input(data)
    
    def get_function_signature(self, function_name: str) -> str:
        """
        Get the function signature.
        
        Args:
            function_name: Function name.
            
        Returns:
            Function signature as hex string.
        """
        if self._contract is None:
            raise ValueError("Contract not initialized")
        
        function = getattr(self._contract.functions, function_name)
        return function._function_identifier


def create_contract(
    address: str,
    contract_type: str = 'custom',
    abi: Optional[List[Dict[str, Any]]] = None,
    web3_client: Optional[Any] = None
) -> Web3Contract:
    """
    Create a contract instance.
    
    Args:
        address: Contract address.
        contract_type: Type of contract ('erc20', 'erc721', 'erc1155', 'custom').
        abi: Contract ABI.
        web3_client: Web3 client instance.
        
    Returns:
        Web3Contract instance.
    """
    return Web3Contract(
        address=address,
        abi=abi,
        web3_client=web3_client,
        contract_type=contract_type
    )


def create_erc20_contract(
    address: str,
    web3_client: Optional[Any] = None
) -> Web3Contract:
    """
    Create an ERC20 contract instance.
    
    Args:
        address: Token contract address.
        web3_client: Web3 client instance.
        
    Returns:
        Web3Contract instance.
    """
    return Web3Contract(
        address=address,
        contract_type='erc20',
        web3_client=web3_client
    )


def create_erc721_contract(
    address: str,
    web3_client: Optional[Any] = None
) -> Web3Contract:
    """
    Create an ERC721 contract instance.
    
    Args:
        address: NFT contract address.
        web3_client: Web3 client instance.
        
    Returns:
        Web3Contract instance.
    """
    return Web3Contract(
        address=address,
        contract_type='erc721',
        web3_client=web3_client
    )


def create_erc1155_contract(
    address: str,
    web3_client: Optional[Any] = None
) -> Web3Contract:
    """
    Create an ERC1155 contract instance.
    
    Args:
        address: Multi-token contract address.
        web3_client: Web3 client instance.
        
    Returns:
        Web3Contract instance.
    """
    return Web3Contract(
        address=address,
        contract_type='erc1155',
        web3_client=web3_client
    )


__all__ = [
    'ContractEvent',
    'ContractCall',
    'ContractTransaction',
    'Web3Contract',
    'create_contract',
    'create_erc20_contract',
    'create_erc721_contract',
    'create_erc1155_contract'
]
