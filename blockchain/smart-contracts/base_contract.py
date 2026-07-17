# blockchain/smart-contracts/base_contract.py
# NEXUS AI TRADING SYSTEM - Base Smart Contract Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Base Smart Contract Integration Class for NEXUS AI Trading System.
Provides core functionality for all contract integrations including:
- Contract initialization and ABI management
- Transaction building and signing
- Gas management and optimization
- Event handling and monitoring
- Error handling and retry logic
- Contract verification
- Multi-chain support
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from web3 import Web3
from web3.contract import Contract
from web3.exceptions import (
    BadFunctionCallOutput,
    ContractLogicError,
    ABIFunctionNotFound,
    ABIFunctionError,
)
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_typing import Address, ChecksumAddress

# NEXUS Imports
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.contract")


# ============================================================================
# Enums & Constants
# ============================================================================

class ContractStatus(str, Enum):
    """Contract status."""
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    ERROR = "error"


class TransactionStatus(str, Enum):
    """Transaction status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REVERTED = "reverted"
    TIMEOUT = "timeout"


@dataclass
class EventData:
    """Event data structure."""
    name: str
    data: Dict[str, Any]
    block_number: int
    transaction_hash: str
    log_index: int
    timestamp: Optional[datetime] = None


@dataclass
class TransactionReceipt:
    """Transaction receipt data."""
    tx_hash: str
    status: TransactionStatus
    block_number: int
    gas_used: int
    gas_price: int
    effective_gas_price: int
    contract_address: Optional[str] = None
    logs: List[Dict[str, Any]] = field(default_factory=list)
    events: List[EventData] = field(default_factory=list)


@dataclass
class ContractMetadata:
    """Contract metadata."""
    name: str
    address: str
    chain_id: int
    abi: List[Dict[str, Any]]
    bytecode: Optional[str] = None
    deployed_at: Optional[datetime] = None
    deployed_by: Optional[str] = None
    version: str = "1.0.0"
    status: ContractStatus = ContractStatus.ACTIVE
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Base Contract Class
# ============================================================================

class BaseContract(ABC):
    """
    Base Smart Contract Integration Class.
    Provides core functionality for all contract integrations.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        contract_name: str,
        contract_address: Union[str, Address],
        abi: Union[List[Dict[str, Any]], str],
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize base contract.

        Args:
            web3_client: Web3 client instance
            contract_name: Contract name
            contract_address: Contract address
            abi: Contract ABI (list or JSON string)
            config: Configuration dictionary
        """
        self.web3_client = web3_client
        self.contract_name = contract_name
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.contract_config = config or {}

        # Parse ABI
        if isinstance(abi, str):
            self.abi = json.loads(abi)
        else:
            self.abi = abi

        # Initialize contract
        self.contract = self.web3_client.get_contract(
            self.contract_address,
            abi=self.abi,
        )

        # State management
        self._running = False
        self._status = ContractStatus.ACTIVE
        self._metadata = self._build_metadata()

        # Gas management
        self._gas_price_multiplier = self.contract_config.get(
            "gas_price_multiplier", 1.2
        )
        self._gas_limit_multiplier = self.contract_config.get(
            "gas_limit_multiplier", 1.3
        )
        self._max_gas_price = self.contract_config.get("max_gas_price", None)
        self._min_gas_price = self.contract_config.get("min_gas_price", None)

        # Transaction management
        self._transaction_timeout = self.contract_config.get(
            "transaction_timeout", 300
        )
        self._confirmation_blocks = self.contract_config.get(
            "confirmation_blocks", 1
        )

        # Event monitoring
        self._event_listeners: Dict[str, List[Callable]] = {}
        self._event_history: List[EventData] = []
        self._event_history_max = self.contract_config.get(
            "event_history_max", 10000
        )

        # Cache
        self._call_cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl = self.contract_config.get("cache_ttl", 60)

        # Performance metrics
        self._performance = {
            "calls": 0,
            "transactions": 0,
            "events": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_call_time_ms": 0.0,
            "avg_transaction_time_ms": 0.0,
        }

        # Initialize
        self._initialize()

        logger.info(
            f"Contract initialized: {contract_name}",
            extra={
                "address": self.contract_address,
                "chain": web3_client.chain_name,
                "chain_id": web3_client.chain_id,
            }
        )

    # -----------------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------------

    def _initialize(self) -> None:
        """Initialize contract-specific setup."""
        # Verify contract exists
        self._verify_contract()

        # Set up event listeners
        self._setup_event_listeners()

    def _verify_contract(self) -> None:
        """Verify contract exists and has code."""
        try:
            code = self.web3_client.get_code(self.contract_address)
            if not code or code == b'':
                logger.warning(
                    f"Contract has no code: {self.contract_address}"
                )
        except Exception as e:
            logger.error(f"Error verifying contract: {e}")

    def _setup_event_listeners(self) -> None:
        """Set up default event listeners."""
        # Override in derived classes
        pass

    def _build_metadata(self) -> ContractMetadata:
        """Build contract metadata."""
        return ContractMetadata(
            name=self.contract_name,
            address=self.contract_address,
            chain_id=self.web3_client.chain_id,
            abi=self.abi,
            status=ContractStatus.ACTIVE,
            version=self.contract_config.get("version", "1.0.0"),
            tags=self.contract_config.get("tags", []),
            metadata=self.contract_config.get("metadata", {}),
        )

    # -----------------------------------------------------------------------
    # Contract Calls
    # -----------------------------------------------------------------------

    async def _call_contract_function(
        self,
        function_name: str,
        *args,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """
        Call a contract function (read-only).

        Args:
            function_name: Function name
            *args: Function arguments
            use_cache: Use cache
            cache_ttl: Cache TTL in seconds
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        start_time = time.time()

        # Build cache key
        cache_key = self._build_cache_key(function_name, args, kwargs)

        # Check cache
        if use_cache and cache_key in self._call_cache:
            result, timestamp = self._call_cache[cache_key]
            ttl = cache_ttl or self._cache_ttl
            if time.time() - timestamp < ttl:
                self._performance["cache_hits"] += 1
                return result

        try:
            func = getattr(self.contract.functions, function_name)
            call_args = {
                "from": kwargs.get("from", self.web3_client.default_account),
            }
            result = await asyncio.to_thread(func(*args).call, call_args)

            # Update performance
            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["calls"] += 1
            self._performance["avg_call_time_ms"] = (
                (self._performance["avg_call_time_ms"] *
                 (self._performance["calls"] - 1) +
                 elapsed_ms) / self._performance["calls"]
            )

            # Cache result
            if use_cache:
                self._call_cache[cache_key] = (result, time.time())

            return result

        except ContractLogicError as e:
            logger.error(f"Contract logic error in {function_name}: {e}")
            raise
        except BadFunctionCallOutput as e:
            logger.error(f"Bad function call in {function_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling {function_name}: {e}")
            raise

    def _build_cache_key(
        self,
        function_name: str,
        args: Tuple,
        kwargs: Dict[str, Any],
    ) -> str:
        """Build cache key for function call."""
        key_parts = [function_name]
        key_parts.extend(str(a) for a in args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        return "_".join(key_parts)

    # -----------------------------------------------------------------------
    # Transaction Building
    # -----------------------------------------------------------------------

    async def _build_transaction(
        self,
        function_name: str,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Build a transaction.

        Args:
            function_name: Function name
            *args: Function arguments
            **kwargs: Transaction parameters

        Returns:
            Transaction dictionary
        """
        try:
            func = getattr(self.contract.functions, function_name)

            # Build transaction
            tx = func(*args).build_transaction({
                "from": kwargs.get("from", self.web3_client.default_account),
                "nonce": kwargs.get(
                    "nonce",
                    await self.web3_client.get_nonce(
                        kwargs.get("from", self.web3_client.default_account)
                    )
                ),
                "gas": kwargs.get("gas", 0),
                "gasPrice": kwargs.get(
                    "gas_price",
                    await self._get_gas_price(),
                ),
            })

            # Estimate gas if not provided
            if tx["gas"] == 0:
                gas = await self._estimate_gas(function_name, *args, **kwargs)
                tx["gas"] = int(gas * self._gas_limit_multiplier)

            return tx

        except Exception as e:
            logger.error(f"Error building transaction: {e}")
            raise

    async def _estimate_gas(
        self,
        function_name: str,
        *args,
        **kwargs,
    ) -> int:
        """
        Estimate gas for a transaction.

        Args:
            function_name: Function name
            *args: Function arguments
            **kwargs: Transaction parameters

        Returns:
            Gas estimate
        """
        try:
            func = getattr(self.contract.functions, function_name)
            tx = func(*args).build_transaction({
                "from": kwargs.get("from", self.web3_client.default_account),
            })
            gas = await self.web3_client.estimate_gas(tx)
            return int(gas)
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}, using default")
            return 500000

    async def _send_transaction(
        self,
        tx: Dict[str, Any],
        from_address: Union[str, Address],
    ) -> Optional[str]:
        """
        Send a transaction.

        Args:
            tx: Transaction dictionary
            from_address: From address

        Returns:
            Transaction hash or None
        """
        start_time = time.time()

        try:
            # Sign transaction
            signed_tx = self.web3_client.sign_transaction(tx, from_address)

            # Send transaction
            tx_hash = await self.web3_client.send_raw_transaction(
                signed_tx.rawTransaction
            )

            # Wait for receipt
            receipt = await self.web3_client.wait_for_transaction_receipt(
                tx_hash,
                timeout=self._transaction_timeout,
            )

            # Update performance
            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["transactions"] += 1
            self._performance["avg_transaction_time_ms"] = (
                (self._performance["avg_transaction_time_ms"] *
                 (self._performance["transactions"] - 1) +
                 elapsed_ms) / self._performance["transactions"]
            )

            if receipt and receipt.get("status", 0) == 1:
                return Web3.to_hex(tx_hash)
            else:
                logger.error(f"Transaction failed: {tx_hash}")
                return None

        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            return None

    async def _get_gas_price(self) -> int:
        """
        Get optimized gas price.

        Returns:
            Gas price in wei
        """
        try:
            gas_price = await self.web3_client.get_gas_price()

            # Apply multiplier
            adjusted_price = int(gas_price * self._gas_price_multiplier)

            # Apply limits
            if self._max_gas_price and adjusted_price > self._max_gas_price:
                adjusted_price = self._max_gas_price

            if self._min_gas_price and adjusted_price < self._min_gas_price:
                adjusted_price = self._min_gas_price

            return adjusted_price

        except Exception as e:
            logger.warning(f"Error getting gas price: {e}, using default")
            return 50000000000  # 50 Gwei

    # -----------------------------------------------------------------------
    # Event Handling
    # -----------------------------------------------------------------------

    def add_event_listener(
        self,
        event_name: str,
        callback: Callable,
    ) -> None:
        """
        Add an event listener.

        Args:
            event_name: Event name
            callback: Callback function
        """
        if event_name not in self._event_listeners:
            self._event_listeners[event_name] = []
        self._event_listeners[event_name].append(callback)

    def remove_event_listener(
        self,
        event_name: str,
        callback: Callable,
    ) -> bool:
        """
        Remove an event listener.

        Args:
            event_name: Event name
            callback: Callback function

        Returns:
            True if removed, False otherwise
        """
        if event_name in self._event_listeners:
            try:
                self._event_listeners[event_name].remove(callback)
                return True
            except ValueError:
                pass
        return False

    async def _emit_event(self, event_data: EventData) -> None:
        """
        Emit an event to listeners.

        Args:
            event_data: Event data
        """
        if event_data.name in self._event_listeners:
            for callback in self._event_listeners[event_data.name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event_data)
                    else:
                        callback(event_data)
                except Exception as e:
                    logger.error(f"Error in event callback: {e}")

        # Store event
        self._event_history.append(event_data)
        if len(self._event_history) > self._event_history_max:
            self._event_history = self._event_history[-self._event_history_max:]

        self._performance["events"] += 1

    async def get_events(
        self,
        event_name: Optional[str] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[EventData]:
        """
        Get events.

        Args:
            event_name: Filter by event name
            from_block: From block number
            to_block: To block number
            limit: Maximum number of events

        Returns:
            List of EventData
        """
        events = self._event_history

        if event_name:
            events = [e for e in events if e.name == event_name]

        if from_block:
            events = [e for e in events if e.block_number >= from_block]

        if to_block:
            events = [e for e in events if e.block_number <= to_block]

        if limit:
            events = events[-limit:]

        return events

    # -----------------------------------------------------------------------
    # Error Handling
    # -----------------------------------------------------------------------

    def _handle_error(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
    ) -> None:
        """
        Handle an error.

        Args:
            error: Exception
            context: Error context
        """
        logger.error(
            f"Contract error: {error}",
            extra={
                "contract": self.contract_name,
                "address": self.contract_address,
                "context": context or {},
                "error": str(error),
            }
        )

    # -----------------------------------------------------------------------
    # Contract Status
    # -----------------------------------------------------------------------

    def get_status(self) -> ContractStatus:
        """Get contract status."""
        return self._status

    def set_status(self, status: ContractStatus) -> None:
        """Set contract status."""
        self._status = status
        logger.info(f"Contract status updated: {status.value}")

    def is_active(self) -> bool:
        """Check if contract is active."""
        return self._status == ContractStatus.ACTIVE

    def is_paused(self) -> bool:
        """Check if contract is paused."""
        return self._status == ContractStatus.PAUSED

    # -----------------------------------------------------------------------
    # Gas Management
    # -----------------------------------------------------------------------

    def set_gas_multipliers(
        self,
        price_multiplier: float,
        limit_multiplier: float,
    ) -> None:
        """Set gas multipliers."""
        self._gas_price_multiplier = price_multiplier
        self._gas_limit_multiplier = limit_multiplier

    def set_gas_limits(
        self,
        min_price: Optional[int],
        max_price: Optional[int],
    ) -> None:
        """Set gas price limits."""
        self._min_gas_price = min_price
        self._max_gas_price = max_price

    # -----------------------------------------------------------------------
    # Cache Management
    # -----------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Clear the call cache."""
        self._call_cache.clear()
        logger.debug("Cache cleared")

    def set_cache_ttl(self, ttl: int) -> None:
        """Set cache TTL."""
        self._cache_ttl = ttl

    # -----------------------------------------------------------------------
    # Performance Metrics
    # -----------------------------------------------------------------------

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "contract_name": self.contract_name,
            "contract_address": self.contract_address,
            "chain_id": self.web3_client.chain_id,
            "cache_size": len(self._call_cache),
            "event_listeners": sum(len(v) for v in self._event_listeners.values()),
            "event_history_size": len(self._event_history),
            "status": self._status.value,
        }

    # -----------------------------------------------------------------------
    # Contract Metadata
    # -----------------------------------------------------------------------

    def get_metadata(self) -> ContractMetadata:
        """Get contract metadata."""
        return self._metadata

    def update_metadata(self, updates: Dict[str, Any]) -> None:
        """Update contract metadata."""
        for key, value in updates.items():
            if hasattr(self._metadata, key):
                setattr(self._metadata, key, value)

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def format_amount(
        self,
        amount: int,
        decimals: int = 18,
    ) -> float:
        """Format amount with proper decimals."""
        return amount / (10 ** decimals)

    def parse_amount(
        self,
        amount: float,
        decimals: int = 18,
    ) -> int:
        """Parse amount to integer with proper decimals."""
        return int(amount * (10 ** decimals))

    def is_contract_address(self, address: str) -> bool:
        """
        Check if an address is a contract.

        Args:
            address: Address to check

        Returns:
            True if contract, False otherwise
        """
        try:
            code = self.web3_client.get_code(address)
            return code is not None and code != b''
        except Exception:
            return False

    def get_address(self) -> str:
        """Get contract address."""
        return self.contract_address

    def get_name(self) -> str:
        """Get contract name."""
        return self.contract_name

    def get_abi(self) -> List[Dict[str, Any]]:
        """Get contract ABI."""
        return self.abi

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the contract integration."""
        if self._running:
            return

        self._running = True
        self._status = ContractStatus.ACTIVE

        logger.info(
            f"Contract started: {self.contract_name}",
            extra={"address": self.contract_address}
        )

    async def stop(self) -> None:
        """Stop the contract integration."""
        self._running = False
        self._status = ContractStatus.ARCHIVED

        # Clear cache
        self.clear_cache()

        logger.info(
            f"Contract stopped: {self.contract_name}",
            extra={"address": self.contract_address}
        )

    async def pause(self) -> None:
        """Pause the contract integration."""
        self._status = ContractStatus.PAUSED
        logger.info(
            f"Contract paused: {self.contract_name}",
            extra={"address": self.contract_address}
        )

    async def resume(self) -> None:
        """Resume the contract integration."""
        self._status = ContractStatus.ACTIVE
        logger.info(
            f"Contract resumed: {self.contract_name}",
            extra={"address": self.contract_address}
        )

    # -----------------------------------------------------------------------
    # Context Manager Support
    # -----------------------------------------------------------------------

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    # -----------------------------------------------------------------------
    # Abstract Methods
    # -----------------------------------------------------------------------

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check.

        Returns:
            Health check results
        """
        raise NotImplementedError


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the base contract
    pass
