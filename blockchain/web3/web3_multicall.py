"""
Web3 Multicall Module
=======================

This module provides multicall functionality for Ethereum and EVM-compatible chains
using the Multicall3 contract. It allows batching multiple contract calls into a
single RPC request, significantly reducing latency and improving performance.

Supports:
- Multicall3 contract integration
- Batch contract calls
- Result aggregation
- Error handling
- Multiple networks
"""

import json
import logging
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from web3 import Web3
from web3.types import BlockIdentifier
from eth_abi import decode_abi, encode_abi
from eth_utils import to_checksum_address

from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.converters import to_int, to_float, to_str
from trading.bots.swing_bot.utils.helpers import load_json, load_yaml

logger = logging.getLogger(__name__)


@dataclass
class MulticallRequest:
    """A single call request for multicall."""
    target: str          # Contract address
    function_name: str   # Function name
    args: List[Any]      # Function arguments
    output_types: Optional[List[str]] = None  # Output types for decoding
    abi: Optional[List[Dict[str, Any]]] = None  # ABI for the function
    call_data: Optional[str] = None  # Pre-encoded call data


@dataclass
class MulticallResult:
    """Result of a multicall request."""
    success: bool
    result: Any
    error: Optional[str] = None
    raw_result: Optional[bytes] = None
    gas_used: Optional[int] = None
    return_data: Optional[str] = None


class Web3Multicall:
    """
    Web3 multicall client for batching contract calls.
    
    Uses the Multicall3 contract to aggregate multiple view function calls
    into a single RPC request. Supports all EVM-compatible chains where
    Multicall3 is deployed.
    """
    
    # Known Multicall3 addresses by chain ID
    MULTICALL3_ADDRESSES = {
        1: "0xcA11bde05977b3631167028862bE2a173976CA11",   # Ethereum Mainnet
        5: "0xcA11bde05977b3631167028862bE2a173976CA11",   # Goerli
        11155111: "0xcA11bde05977b3631167028862bE2a173976CA11",  # Sepolia
        137: "0xcA11bde05977b3631167028862bE2a173976CA11",  # Polygon
        42161: "0xcA11bde05977b3631167028862bE2a173976CA11",  # Arbitrum
        10: "0xcA11bde05977b3631167028862bE2a173976CA11",   # Optimism
        56: "0xcA11bde05977b3631167028862bE2a173976CA11",   # BSC
        43114: "0xcA11bde05977b3631167028862bE2a173976CA11", # Avalanche
        250: "0xcA11bde05977b3631167028862bE2a173976CA11",  # Fantom
        100: "0xcA11bde05977b3631167028862bE2a173976CA11",  # Gnosis
        8453: "0xcA11bde05977b3631167028862bE2a173976CA11",  # Base
        59144: "0xcA11bde05977b3631167028862bE2a173976CA11", # Linea
        324: "0xcA11bde05977b3631167028862bE2a173976CA11",   # zkSync Era
        534352: "0xcA11bde05977b3631167028862bE2a173976CA11", # Scroll
    }
    
    # Multicall3 ABI (minimal for aggregate3)
    MULTICALL3_ABI = [
        {
            "inputs": [
                {"name": "calls", "type": "tuple[]", "components": [
                    {"name": "target", "type": "address"},
                    {"name": "allowFailure", "type": "bool"},
                    {"name": "callData", "type": "bytes"}
                ]}
            ],
            "name": "aggregate3",
            "outputs": [
                {"name": "returnData", "type": "tuple[]", "components": [
                    {"name": "success", "type": "bool"},
                    {"name": "returnData", "type": "bytes"}
                ]}
            ],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "calls", "type": "tuple[]", "components": [
                    {"name": "target", "type": "address"},
                    {"name": "callData", "type": "bytes"}
                ]}
            ],
            "name": "aggregate",
            "outputs": [
                {"name": "blockNumber", "type": "uint256"},
                {"name": "returnData", "type": "bytes[]"}
            ],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "calls", "type": "tuple[]", "components": [
                    {"name": "target", "type": "address"},
                    {"name": "allowFailure", "type": "bool"},
                    {"name": "callData", "type": "bytes"}
                ]}
            ],
            "name": "aggregate3Value",
            "outputs": [
                {"name": "returnData", "type": "tuple[]", "components": [
                    {"name": "success", "type": "bool"},
                    {"name": "returnData", "type": "bytes"},
                    {"name": "gasUsed", "type": "uint256"}
                ]}
            ],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "calls", "type": "tuple[]", "components": [
                    {"name": "target", "type": "address"},
                    {"name": "allowFailure", "type": "bool"},
                    {"name": "value", "type": "uint256"},
                    {"name": "callData", "type": "bytes"}
                ]}
            ],
            "name": "aggregate3Value",
            "outputs": [
                {"name": "returnData", "type": "tuple[]", "components": [
                    {"name": "success", "type": "bool"},
                    {"name": "returnData", "type": "bytes"},
                    {"name": "gasUsed", "type": "uint256"}
                ]}
            ],
            "stateMutability": "payable",
            "type": "function"
        }
    ]
    
    def __init__(
        self,
        web3_client: Any,
        multicall_address: Optional[str] = None,
        batch_size: int = 100,
        auto_aggregate: bool = True
    ):
        """
        Initialize the multicall client.
        
        Args:
            web3_client: Web3 client instance.
            multicall_address: Custom Multicall3 address (auto-detected if None).
            batch_size: Maximum number of calls per batch.
            auto_aggregate: Automatically aggregate calls.
        """
        self.web3_client = web3_client
        self.batch_size = batch_size
        self.auto_aggregate = auto_aggregate
        
        # Determine chain ID
        self.chain_id = self.web3_client.chain_id
        
        # Set multicall address
        if multicall_address is not None:
            self.multicall_address = to_checksum_address(multicall_address)
        else:
            self.multicall_address = self.MULTICALL3_ADDRESSES.get(self.chain_id)
            if self.multicall_address is None:
                # Try to detect from chain
                # Fallback: use mainnet address (will fail if not deployed)
                self.multicall_address = self.MULTICALL3_ADDRESSES.get(1)
                if self.multicall_address is None:
                    raise ValueError(f"Multicall3 not available for chain {self.chain_id}")
            else:
                self.multicall_address = to_checksum_address(self.multicall_address)
        
        # Initialize contract
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        self._contract = w3.eth.contract(
            address=self.multicall_address,
            abi=self.MULTICALL3_ABI
        )
        
        # Request queue
        self._calls: List[MulticallRequest] = []
        
        logger.info(f"Web3Multicall initialized with address: {self.multicall_address}")
    
    # ============ Call Management ============
    
    def add_call(
        self,
        target: str,
        function_name: str,
        *args,
        output_types: Optional[List[str]] = None,
        abi: Optional[List[Dict[str, Any]]] = None,
        allow_failure: bool = True
    ) -> 'Web3Multicall':
        """
        Add a call to the batch.
        
        Args:
            target: Contract address.
            function_name: Function name.
            *args: Function arguments.
            output_types: Output types for decoding.
            abi: Contract ABI for the function.
            allow_failure: Allow failure for this call.
            
        Returns:
            Self for chaining.
        """
        # Validate target address
        target = to_checksum_address(target)
        
        # Encode call data
        call_data = self._encode_call_data(target, function_name, *args, abi=abi)
        
        request = MulticallRequest(
            target=target,
            function_name=function_name,
            args=list(args),
            output_types=output_types,
            abi=abi,
            call_data=call_data
        )
        self._calls.append(request)
        
        return self
    
    def add_erc20_balance(self, token_address: str, owner_address: str) -> 'Web3Multicall':
        """
        Convenience method to add an ERC20 balance check.
        
        Args:
            token_address: Token contract address.
            owner_address: Owner address.
            
        Returns:
            Self for chaining.
        """
        return self.add_call(
            token_address,
            'balanceOf',
            owner_address,
            output_types=['uint256']
        )
    
    def add_erc20_allowance(
        self,
        token_address: str,
        owner_address: str,
        spender_address: str
    ) -> 'Web3Multicall':
        """
        Convenience method to add an ERC20 allowance check.
        
        Args:
            token_address: Token contract address.
            owner_address: Owner address.
            spender_address: Spender address.
            
        Returns:
            Self for chaining.
        """
        return self.add_call(
            token_address,
            'allowance',
            owner_address,
            spender_address,
            output_types=['uint256']
        )
    
    def add_erc20_decimals(self, token_address: str) -> 'Web3Multicall':
        """
        Convenience method to add an ERC20 decimals check.
        
        Args:
            token_address: Token contract address.
            
        Returns:
            Self for chaining.
        """
        return self.add_call(
            token_address,
            'decimals',
            output_types=['uint8']
        )
    
    def clear_calls(self) -> None:
        """Clear all pending calls."""
        self._calls.clear()
    
    def get_pending_calls(self) -> List[MulticallRequest]:
        """Get pending calls."""
        return self._calls.copy()
    
    # ============ Encoding / Decoding ============
    
    def _encode_call_data(
        self,
        target: str,
        function_name: str,
        *args,
        abi: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Encode a function call as hex data.
        
        Args:
            target: Contract address.
            function_name: Function name.
            *args: Function arguments.
            abi: Contract ABI (optional).
            
        Returns:
            Hex-encoded call data.
        """
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        # Try to use provided ABI or minimal ERC-20 for common functions
        if abi is None:
            # Fallback: use generic ABI
            abi = [{
                "constant": True,
                "inputs": [{"name": f"arg{i}", "type": "address"} for i in range(len(args))],
                "name": function_name,
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }]
        
        contract = w3.eth.contract(address=target, abi=abi)
        func = getattr(contract.functions, function_name)
        try:
            data = func(*args).build_transaction({'from': '0x0000000000000000000000000000000000000000'})['data']
            return data.hex()
        except Exception as e:
            # If building fails, try fallback method using function signature
            logger.warning(f"Failed to build transaction for {function_name}: {e}")
            return self._encode_function_signature(function_name, args)
    
    def _encode_function_signature(self, function_name: str, args: List[Any]) -> str:
        """
        Encode function call using manual signature.
        
        Args:
            function_name: Function name.
            args: Function arguments.
            
        Returns:
            Hex-encoded call data.
        """
        # Build signature
        signature = f"{function_name}({','.join([self._get_abi_type(arg) for arg in args])})"
        hash = Web3.keccak(text=signature)
        method_id = hash[:4].hex()
        
        # Encode arguments
        encoded_args = b''
        for arg in args:
            if isinstance(arg, str) and arg.startswith('0x') and len(arg) == 42:
                # Address
                encoded_args += Web3.to_bytes(hexstr=arg)
            elif isinstance(arg, int):
                # Integer
                encoded_args += arg.to_bytes(32, 'big')
            elif isinstance(arg, bool):
                encoded_args += (1).to_bytes(32, 'big') if arg else (0).to_bytes(32, 'big')
            else:
                # String or bytes
                if isinstance(arg, str):
                    arg_bytes = arg.encode()
                elif isinstance(arg, bytes):
                    arg_bytes = arg
                else:
                    arg_bytes = str(arg).encode()
                encoded_args += len(arg_bytes).to_bytes(32, 'big') + arg_bytes
        
        return method_id + encoded_args.hex()
    
    def _get_abi_type(self, value: Any) -> str:
        """Get ABI type for a value."""
        if isinstance(value, str) and value.startswith('0x') and len(value) == 42:
            return 'address'
        elif isinstance(value, int):
            return 'uint256'
        elif isinstance(value, bool):
            return 'bool'
        elif isinstance(value, (bytes, bytearray)):
            return 'bytes'
        else:
            return 'string'
    
    def _decode_output(
        self,
        output_data: bytes,
        output_types: Optional[List[str]]
    ) -> Any:
        """
        Decode contract function output.
        
        Args:
            output_data: Raw output data.
            output_types: Output types.
            
        Returns:
            Decoded output.
        """
        if not output_data or output_data == b'':
            return None
        
        if output_types is None:
            # Try to determine from data
            if len(output_data) == 32:
                # Probably a single uint256
                return int.from_bytes(output_data, 'big')
            else:
                return output_data.hex()
        
        try:
            decoded = decode_abi(output_types, output_data)
            if len(decoded) == 1:
                return decoded[0]
            return decoded
        except Exception as e:
            logger.warning(f"Failed to decode output: {e}")
            return output_data.hex()
    
    # ============ Execution ============
    
    def execute(
        self,
        block_identifier: BlockIdentifier = 'latest',
        aggregate_method: str = 'aggregate3'
    ) -> List[MulticallResult]:
        """
        Execute all pending calls.
        
        Args:
            block_identifier: Block to query.
            aggregate_method: Multicall method to use ('aggregate3', 'aggregate').
            
        Returns:
            List of MulticallResult objects.
        """
        if not self._calls:
            return []
        
        results = []
        
        # Split calls into batches
        for i in range(0, len(self._calls), self.batch_size):
            batch = self._calls[i:i + self.batch_size]
            batch_results = self._execute_batch(batch, block_identifier, aggregate_method)
            results.extend(batch_results)
        
        return results
    
    def _execute_batch(
        self,
        batch: List[MulticallRequest],
        block_identifier: BlockIdentifier,
        aggregate_method: str
    ) -> List[MulticallResult]:
        """
        Execute a batch of calls.
        
        Args:
            batch: List of MulticallRequest objects.
            block_identifier: Block to query.
            aggregate_method: Multicall method.
            
        Returns:
            List of MulticallResult objects.
        """
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        # Build calls for Multicall3
        multicall_calls = []
        for request in batch:
            target = request.target
            call_data = request.call_data
            
            if aggregate_method == 'aggregate3':
                # aggregate3 expects (target, allowFailure, callData)
                multicall_calls.append((target, True, call_data))
            elif aggregate_method == 'aggregate':
                # aggregate expects (target, callData)
                multicall_calls.append((target, call_data))
            else:
                raise ValueError(f"Unsupported aggregate method: {aggregate_method}")
        
        try:
            # Call Multicall3
            if aggregate_method == 'aggregate3':
                # aggregate3 returns (success, returnData)
                raw_results = self._contract.functions.aggregate3(multicall_calls).call(
                    block_identifier=block_identifier
                )
            elif aggregate_method == 'aggregate':
                # aggregate returns (blockNumber, returnData)
                block_num, return_data = self._contract.functions.aggregate(multicall_calls).call(
                    block_identifier=block_identifier
                )
                raw_results = [(True, data) for data in return_data]
            else:
                raise ValueError(f"Unsupported aggregate method: {aggregate_method}")
            
            # Process results
            results = []
            for i, request in enumerate(batch):
                success, data = raw_results[i]
                result = MulticallResult(
                    success=success,
                    raw_result=data
                )
                
                if success and data:
                    try:
                        decoded = self._decode_output(data, request.output_types)
                        result.result = decoded
                    except Exception as e:
                        result.success = False
                        result.error = str(e)
                elif not success:
                    result.error = "Call failed"
                
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Multicall execution failed: {e}")
            # Return error results for all calls
            return [
                MulticallResult(
                    success=False,
                    result=None,
                    error=str(e)
                )
                for _ in batch
            ]
    
    def execute_single(
        self,
        target: str,
        function_name: str,
        *args,
        output_types: Optional[List[str]] = None,
        abi: Optional[List[Dict[str, Any]]] = None,
        block_identifier: BlockIdentifier = 'latest'
    ) -> Any:
        """
        Execute a single call using multicall.
        
        Args:
            target: Contract address.
            function_name: Function name.
            *args: Function arguments.
            output_types: Output types.
            abi: Contract ABI.
            block_identifier: Block to query.
            
        Returns:
            Decoded result.
        """
        self.clear_calls()
        self.add_call(target, function_name, *args, output_types=output_types, abi=abi)
        results = self.execute(block_identifier)
        
        if results and results[0].success:
            return results[0].result
        else:
            error = results[0].error if results else "No result"
            raise RuntimeError(f"Multicall failed: {error}")
    
    # ============ Batch Aggregation ============
    
    def execute_aggregated(
        self,
        calls: List[Tuple[str, str, Tuple, Optional[List[str]], Optional[List]]],
        block_identifier: BlockIdentifier = 'latest'
    ) -> List[MulticallResult]:
        """
        Execute multiple calls in one batch.
        
        Args:
            calls: List of (target, function_name, args, output_types, abi)
            block_identifier: Block to query.
            
        Returns:
            List of MulticallResult objects.
        """
        self.clear_calls()
        for target, func, args, outputs, abi in calls:
            self.add_call(target, func, *args, output_types=outputs, abi=abi)
        return self.execute(block_identifier)
    
    # ============ Utility Methods ============
    
    def get_contract_function_abi(
        self,
        contract_address: str,
        function_name: str,
        contract_abi: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Get the ABI of a specific function.
        
        Args:
            contract_address: Contract address.
            function_name: Function name.
            contract_abi: Full contract ABI.
            
        Returns:
            Function ABI or None.
        """
        for item in contract_abi:
            if item.get('type') == 'function' and item.get('name') == function_name:
                return item
        return None
    
    def get_multicall_address(self) -> str:
        """Get the current Multicall3 address."""
        return self.multicall_address
    
    def get_pending_count(self) -> int:
        """Get number of pending calls."""
        return len(self._calls)


def create_multicall(
    web3_client: Any,
    multicall_address: Optional[str] = None,
    batch_size: int = 100
) -> Web3Multicall:
    """
    Create a Web3 multicall instance.
    
    Args:
        web3_client: Web3 client instance.
        multicall_address: Custom Multicall3 address.
        batch_size: Batch size.
        
    Returns:
        Web3Multicall instance.
    """
    return Web3Multicall(
        web3_client=web3_client,
        multicall_address=multicall_address,
        batch_size=batch_size
    )


__all__ = [
    'MulticallRequest',
    'MulticallResult',
    'Web3Multicall',
    'create_multicall'
]
