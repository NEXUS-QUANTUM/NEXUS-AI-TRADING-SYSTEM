"""
Web3 Transaction Module
==========================

This module provides transaction management capabilities for Web3 clients.
It supports creating, signing, sending, and tracking transactions on Ethereum
and EVM-compatible chains with automatic retry, nonce management, and gas optimization.

Supports:
- Transaction creation and signing
- Sending with retry and fallback
- Transaction status tracking
- Nonce management
- EIP-1559 and legacy transactions
- Transaction replacement (speed up, cancel)
- Batch transactions
- Pending transaction monitoring
- Transaction history and filtering
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
from decimal import Decimal

from web3 import Web3
from web3.types import TxParams, Wei, HexBytes, BlockIdentifier, TxReceipt
from eth_account import Account
from eth_account.signers.local import LocalAccount
from hexbytes import HexBytes
from eth_utils import to_checksum_address, to_wei, from_wei

from trading.bots.swing_bot.utils.cache import MemoryCache
from trading.bots.swing_bot.utils.converters import to_int, to_float, to_str
from trading.bots.swing_bot.utils.validators import validate_data

from .web3_gas import GasManager, create_gas_manager

logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """Transaction status states."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SPEED_UP = "speed_up"
    REPLACED = "replaced"
    TIMEOUT = "timeout"


class TransactionType(Enum):
    """Transaction types."""
    LEGACY = "legacy"
    EIP1559 = "eip1559"


@dataclass
class Transaction:
    """Transaction data structure."""
    hash: str
    from_address: str
    to_address: str
    value: float
    data: Optional[str] = None
    gas_limit: int = 0
    gas_price: int = 0
    max_fee_per_gas: Optional[int] = None
    max_priority_fee_per_gas: Optional[int] = None
    nonce: int = 0
    chain_id: int = 0
    status: TransactionStatus = TransactionStatus.PENDING
    tx_type: TransactionType = TransactionType.LEGACY
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    block_number: Optional[int] = None
    block_hash: Optional[str] = None
    gas_used: Optional[int] = None
    effective_gas_price: Optional[int] = None
    receipt: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 0
    original_hash: Optional[str] = None
    replacement_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionOptions:
    """Transaction options for sending."""
    nonce: Optional[int] = None
    gas_limit: Optional[int] = None
    gas_price: Optional[int] = None
    max_fee_per_gas: Optional[int] = None
    max_priority_fee_per_gas: Optional[int] = None
    gas_strategy: str = "standard"
    timeout: int = 120
    confirmations: int = 1
    replaceable: bool = True
    speed_up_factor: float = 1.2
    max_speed_up_count: int = 3


class Web3TransactionManager:
    """
    Web3 transaction manager for sending and tracking transactions.
    
    Supports:
    - Transaction creation and signing
    - Nonce management
    - Gas optimization
    - Transaction replacement (speed up, cancel)
    - Pending transaction monitoring
    - Batch transactions
    - Transaction history
    """
    
    def __init__(
        self,
        web3_client: Any,
        gas_manager: Optional[GasManager] = None,
        default_options: Optional[TransactionOptions] = None,
        max_pending_tx: int = 100,
        enable_pending_monitor: bool = True,
        pending_monitor_interval: int = 30,
        cache_ttl: int = 300
    ):
        """
        Initialize the transaction manager.
        
        Args:
            web3_client: Web3 client instance.
            gas_manager: Gas manager instance (auto-created if None).
            default_options: Default transaction options.
            max_pending_tx: Maximum pending transactions to track.
            enable_pending_monitor: Enable pending transaction monitoring.
            pending_monitor_interval: Pending monitor interval in seconds.
            cache_ttl: Cache TTL in seconds.
        """
        self.web3_client = web3_client
        
        # Initialize gas manager
        if gas_manager is None:
            self.gas_manager = create_gas_manager(web3_client)
        else:
            self.gas_manager = gas_manager
        
        # Default options
        self.default_options = default_options or TransactionOptions()
        
        # Transaction tracking
        self._transactions: Dict[str, Transaction] = {}
        self._pending_transactions: Dict[str, Transaction] = {}
        self._nonce_lock = asyncio.Lock()
        self._lock = threading.RLock()
        
        # History
        self._history: deque = deque(maxlen=1000)
        
        # Cache
        self._cache = MemoryCache(max_size=1000, default_ttl=cache_ttl)
        
        # Pending monitor
        self._enable_pending_monitor = enable_pending_monitor
        self._pending_monitor_interval = pending_monitor_interval
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Start monitor
        if enable_pending_monitor:
            self._start_monitor()
        
        logger.info("Web3TransactionManager initialized")
    
    # ============ Pending Monitor ============
    
    def _start_monitor(self) -> None:
        """Start the pending transaction monitor."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="tx_monitor"
        )
        self._monitor_thread.start()
        logger.info("Pending transaction monitor started")
    
    def _monitor_loop(self) -> None:
        """Monitor pending transactions."""
        while self._running:
            try:
                self._check_pending_transactions()
                time.sleep(self._pending_monitor_interval)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(5)
    
    def _check_pending_transactions(self) -> None:
        """Check status of pending transactions."""
        with self._lock:
            pending = list(self._pending_transactions.values())
        
        for tx in pending:
            # Check if transaction is still pending
            if tx.status not in [TransactionStatus.PENDING, TransactionStatus.SUBMITTED]:
                continue
            
            # Check if transaction has timed out
            if tx.submitted_at:
                timeout = self.default_options.timeout
                if (datetime.now() - tx.submitted_at).total_seconds() > timeout:
                    self._update_transaction_status(tx.hash, TransactionStatus.TIMEOUT)
                    logger.warning(f"Transaction {tx.hash} timed out")
                    continue
            
            # Check transaction receipt
            receipt = self.get_transaction_receipt(tx.hash)
            if receipt:
                status = receipt.get('status')
                if status == 1:
                    self._handle_confirmed_transaction(tx, receipt)
                elif status == 0:
                    self._handle_failed_transaction(tx, receipt)
    
    def _handle_confirmed_transaction(self, tx: Transaction, receipt: Dict[str, Any]) -> None:
        """Handle confirmed transaction."""
        tx.status = TransactionStatus.CONFIRMED
        tx.confirmed_at = datetime.now()
        tx.block_number = receipt.get('blockNumber')
        tx.block_hash = receipt.get('blockHash')
        tx.gas_used = receipt.get('gasUsed')
        tx.effective_gas_price = receipt.get('effectiveGasPrice')
        tx.receipt = receipt
        
        self._update_transaction_status(tx.hash, TransactionStatus.CONFIRMED)
        logger.info(f"Transaction {tx.hash} confirmed at block {tx.block_number}")
    
    def _handle_failed_transaction(self, tx: Transaction, receipt: Dict[str, Any]) -> None:
        """Handle failed transaction."""
        tx.status = TransactionStatus.FAILED
        tx.receipt = receipt
        tx.error = "Transaction failed on-chain"
        
        self._update_transaction_status(tx.hash, TransactionStatus.FAILED)
        logger.warning(f"Transaction {tx.hash} failed")
    
    # ============ Transaction Creation ============
    
    def build_transaction(
        self,
        to: str,
        value: Union[float, int, str] = 0,
        data: Optional[str] = None,
        options: Optional[TransactionOptions] = None,
        from_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a transaction dictionary.
        
        Args:
            to: Recipient address.
            value: Value in ETH (float).
            data: Transaction data.
            options: Transaction options.
            from_address: Sender address.
            
        Returns:
            Transaction dictionary.
        """
        if from_address is None:
            if self.web3_client._account:
                from_address = self.web3_client._account.address
            else:
                raise ValueError("No from address provided and no account set")
        
        from_address = to_checksum_address(from_address)
        to = to_checksum_address(to)
        
        options = options or self.default_options
        
        # Get nonce
        nonce = options.nonce
        if nonce is None:
            nonce = self.web3_client._call_with_failover(
                lambda w: w.eth.get_transaction_count(from_address)
            )
        
        # Get gas price
        gas_price = options.gas_price
        max_fee = options.max_fee_per_gas
        max_priority = options.max_priority_fee_per_gas
        
        if gas_price is None and max_fee is None:
            # Use gas manager
            if self.web3_client.is_eip1559_supported():
                max_fee, max_priority = self.gas_manager.get_eip1559_fees(
                    options.gas_strategy
                )
            else:
                gas_price = self.gas_manager.get_gas_price_for_strategy(
                    options.gas_strategy
                )
        
        # Build transaction
        tx: TxParams = {
            'from': from_address,
            'to': to,
            'value': Web3.to_wei(value, 'ether'),
            'nonce': nonce,
            'chainId': self.web3_client.chain_id,
        }
        
        if data:
            tx['data'] = data
        
        # Gas limit
        if options.gas_limit:
            tx['gas'] = options.gas_limit
        else:
            tx['gas'] = self._estimate_gas(tx)
        
        # Fee strategy
        if max_fee is not None and max_priority is not None:
            tx['maxFeePerGas'] = max_fee
            tx['maxPriorityFeePerGas'] = max_priority
            tx['type'] = '0x2'
        elif gas_price is not None:
            tx['gasPrice'] = gas_price
        else:
            # Fallback
            tx['gasPrice'] = self.gas_manager.get_gas_price_for_strategy(
                options.gas_strategy
            )
        
        return tx
    
    def _estimate_gas(self, tx: Dict[str, Any]) -> int:
        """Estimate gas for a transaction."""
        try:
            gas = self.web3_client._call_with_failover(
                lambda w: w.eth.estimate_gas(tx)
            )
            return int(gas * 1.1)  # Add buffer
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}")
            return 21000  # Default for ETH transfer
    
    def sign_transaction(self, tx: Dict[str, Any]) -> bytes:
        """
        Sign a transaction.
        
        Args:
            tx: Transaction dictionary.
            
        Returns:
            Signed transaction as bytes.
        """
        if not self.web3_client._account:
            raise ValueError("No private key set")
        
        signed = self.web3_client._account.sign_transaction(tx)
        return signed.raw_transaction
    
    # ============ Sending Transactions ============
    
    def send_transaction(
        self,
        to: str,
        value: Union[float, int, str] = 0,
        data: Optional[str] = None,
        options: Optional[TransactionOptions] = None,
        from_address: Optional[str] = None,
        sign: bool = True
    ) -> Transaction:
        """
        Send a transaction.
        
        Args:
            to: Recipient address.
            value: Value in ETH.
            data: Transaction data.
            options: Transaction options.
            from_address: Sender address.
            sign: Sign the transaction.
            
        Returns:
            Transaction object.
        """
        # Build transaction
        tx_dict = self.build_transaction(to, value, data, options, from_address)
        
        # Sign if needed
        if sign:
            signed_tx = self.sign_transaction(tx_dict)
            raw_tx = signed_tx
        else:
            raw_tx = tx_dict
        
        # Send transaction
        return self._send_raw_transaction(raw_tx, tx_dict, sign)
    
    def _send_raw_transaction(
        self,
        raw_tx: Union[bytes, Dict[str, Any]],
        tx_dict: Dict[str, Any],
        signed: bool
    ) -> Transaction:
        """Send a raw transaction."""
        try:
            if signed:
                tx_hash = self.web3_client._call_with_failover(
                    lambda w: w.eth.send_raw_transaction(raw_tx)
                )
            else:
                tx_hash = self.web3_client._call_with_failover(
                    lambda w: w.eth.send_transaction(raw_tx)
                )
            
            tx_hash_hex = tx_hash.hex() if isinstance(tx_hash, HexBytes) else tx_hash
            
            # Create transaction record
            transaction = Transaction(
                hash=tx_hash_hex,
                from_address=tx_dict['from'],
                to_address=tx_dict['to'],
                value=Web3.from_wei(tx_dict['value'], 'ether'),
                data=tx_dict.get('data'),
                gas_limit=tx_dict['gas'],
                gas_price=tx_dict.get('gasPrice', 0),
                max_fee_per_gas=tx_dict.get('maxFeePerGas'),
                max_priority_fee_per_gas=tx_dict.get('maxPriorityFeePerGas'),
                nonce=tx_dict['nonce'],
                chain_id=tx_dict['chainId'],
                status=TransactionStatus.SUBMITTED,
                tx_type=TransactionType.EIP1559 if 'maxFeePerGas' in tx_dict else TransactionType.LEGACY,
                submitted_at=datetime.now(),
                attempts=1
            )
            
            # Store transaction
            self._add_transaction(transaction)
            
            logger.info(f"Transaction sent: {tx_hash_hex}")
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to send transaction: {e}")
            raise
    
    def send_contract_transaction(
        self,
        contract_address: str,
        function_name: str,
        *args,
        value: Union[float, int, str] = 0,
        options: Optional[TransactionOptions] = None,
        from_address: Optional[str] = None,
        abi: Optional[List[Dict[str, Any]]] = None
    ) -> Transaction:
        """
        Send a contract transaction.
        
        Args:
            contract_address: Contract address.
            function_name: Function name.
            *args: Function arguments.
            value: Value in ETH.
            options: Transaction options.
            from_address: Sender address.
            abi: Contract ABI.
            
        Returns:
            Transaction object.
        """
        from_address = from_address or self.web3_client.address
        
        # Get contract
        from .web3_contract import Web3Contract
        contract = Web3Contract(
            address=contract_address,
            abi=abi,
            web3_client=self.web3_client
        )
        
        # Encode function call
        data = contract.encode_function_call(function_name, *args)
        
        # Build and send transaction
        return self.send_transaction(
            to=contract_address,
            value=value,
            data=data,
            options=options,
            from_address=from_address
        )
    
    # ============ Transaction Management ============
    
    def _add_transaction(self, tx: Transaction) -> None:
        """Add a transaction to tracking."""
        with self._lock:
            self._transactions[tx.hash] = tx
            
            if tx.status in [TransactionStatus.PENDING, TransactionStatus.SUBMITTED]:
                self._pending_transactions[tx.hash] = tx
            
            self._history.append(tx)
    
    def _update_transaction_status(self, tx_hash: str, status: TransactionStatus) -> None:
        """Update transaction status."""
        with self._lock:
            if tx_hash in self._transactions:
                self._transactions[tx_hash].status = status
                
                if status in [TransactionStatus.CONFIRMED, TransactionStatus.FAILED]:
                    self._pending_transactions.pop(tx_hash, None)
    
    def get_transaction(self, tx_hash: str) -> Optional[Transaction]:
        """
        Get transaction by hash.
        
        Args:
            tx_hash: Transaction hash.
            
        Returns:
            Transaction object or None.
        """
        with self._lock:
            return self._transactions.get(tx_hash)
    
    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get transaction receipt.
        
        Args:
            tx_hash: Transaction hash.
            
        Returns:
            Receipt dictionary or None.
        """
        return self.web3_client.get_transaction_receipt(tx_hash)
    
    def wait_for_confirmation(
        self,
        tx_hash: str,
        timeout: Optional[int] = None,
        confirmations: int = 1
    ) -> Optional[Transaction]:
        """
        Wait for transaction confirmation.
        
        Args:
            tx_hash: Transaction hash.
            timeout: Timeout in seconds.
            confirmations: Number of confirmations.
            
        Returns:
            Transaction object or None.
        """
        timeout = timeout or self.default_options.timeout
        
        # Get transaction
        tx = self.get_transaction(tx_hash)
        if tx is None:
            # Try to fetch from chain
            receipt = self.get_transaction_receipt(tx_hash)
            if receipt:
                tx = self._create_from_receipt(receipt)
        
        if tx is None:
            raise ValueError(f"Transaction {tx_hash} not found")
        
        # Wait for receipt
        start_time = time.time()
        while time.time() - start_time < timeout:
            receipt = self.get_transaction_receipt(tx_hash)
            if receipt:
                status = receipt.get('status')
                if status == 1:
                    tx.status = TransactionStatus.CONFIRMED
                    tx.confirmed_at = datetime.now()
                    tx.block_number = receipt.get('blockNumber')
                    tx.block_hash = receipt.get('blockHash')
                    tx.gas_used = receipt.get('gasUsed')
                    tx.effective_gas_price = receipt.get('effectiveGasPrice')
                    tx.receipt = receipt
                    
                    self._update_transaction_status(tx_hash, TransactionStatus.CONFIRMED)
                    return tx
                elif status == 0:
                    tx.status = TransactionStatus.FAILED
                    tx.receipt = receipt
                    self._update_transaction_status(tx_hash, TransactionStatus.FAILED)
                    return tx
            
            time.sleep(1)
        
        # Timeout
        self._update_transaction_status(tx_hash, TransactionStatus.TIMEOUT)
        return None
    
    def _create_from_receipt(self, receipt: Dict[str, Any]) -> Transaction:
        """Create transaction from receipt."""
        tx = Transaction(
            hash=receipt.get('transactionHash', ''),
            from_address=receipt.get('from', ''),
            to_address=receipt.get('to', ''),
            value=0,
            gas_limit=receipt.get('gasUsed', 0),
            nonce=0,
            chain_id=self.web3_client.chain_id,
            status=TransactionStatus.CONFIRMED if receipt.get('status') == 1 else TransactionStatus.FAILED,
            confirmed_at=datetime.now(),
            block_number=receipt.get('blockNumber'),
            block_hash=receipt.get('blockHash'),
            gas_used=receipt.get('gasUsed'),
            effective_gas_price=receipt.get('effectiveGasPrice'),
            receipt=receipt
        )
        
        self._add_transaction(tx)
        return tx
    
    # ============ Transaction Replacement ============
    
    def speed_up_transaction(
        self,
        tx_hash: str,
        gas_price_multiplier: Optional[float] = None
    ) -> Optional[Transaction]:
        """
        Speed up a pending transaction.
        
        Args:
            tx_hash: Transaction hash.
            gas_price_multiplier: Multiplier for gas price.
            
        Returns:
            New Transaction or None.
        """
        tx = self.get_transaction(tx_hash)
        if tx is None:
            logger.warning(f"Transaction {tx_hash} not found")
            return None
        
        if tx.status not in [TransactionStatus.PENDING, TransactionStatus.SUBMITTED]:
            logger.warning(f"Transaction {tx_hash} is not pending")
            return None
        
        multiplier = gas_price_multiplier or self.default_options.speed_up_factor
        
        # Build replacement transaction
        if tx.tx_type == TransactionType.EIP1559:
            new_max_fee = int(tx.max_fee_per_gas * multiplier)
            new_max_priority = int(tx.max_priority_fee_per_gas * multiplier)
            options = TransactionOptions(
                nonce=tx.nonce,
                gas_limit=tx.gas_limit,
                max_fee_per_gas=new_max_fee,
                max_priority_fee_per_gas=new_max_priority,
                gas_strategy="urgent"
            )
        else:
            new_gas_price = int(tx.gas_price * multiplier)
            options = TransactionOptions(
                nonce=tx.nonce,
                gas_limit=tx.gas_limit,
                gas_price=new_gas_price,
                gas_strategy="urgent"
            )
        
        # Send replacement
        try:
            new_tx = self.send_transaction(
                to=tx.to_address,
                value=tx.value,
                data=tx.data,
                options=options,
                from_address=tx.from_address
            )
            
            # Link transactions
            new_tx.original_hash = tx.hash
            new_tx.metadata['replaces'] = tx.hash
            tx.replacement_hash = new_tx.hash
            tx.status = TransactionStatus.SPEED_UP
            
            self._update_transaction_status(tx.hash, TransactionStatus.SPEED_UP)
            
            logger.info(f"Transaction {tx_hash} sped up: {new_tx.hash}")
            return new_tx
            
        except Exception as e:
            logger.error(f"Failed to speed up transaction: {e}")
            return None
    
    def cancel_transaction(self, tx_hash: str) -> Optional[Transaction]:
        """
        Cancel a pending transaction.
        
        Args:
            tx_hash: Transaction hash.
            
        Returns:
            Cancellation transaction or None.
        """
        tx = self.get_transaction(tx_hash)
        if tx is None:
            logger.warning(f"Transaction {tx_hash} not found")
            return None
        
        if tx.status not in [TransactionStatus.PENDING, TransactionStatus.SUBMITTED]:
            logger.warning(f"Transaction {tx_hash} is not pending")
            return None
        
        # Send cancellation transaction (send 0 ETH to self)
        try:
            options = TransactionOptions(
                nonce=tx.nonce,
                gas_strategy="urgent"
            )
            
            cancel_tx = self.send_transaction(
                to=tx.from_address,
                value=0,
                options=options,
                from_address=tx.from_address
            )
            
            # Link transactions
            cancel_tx.original_hash = tx.hash
            cancel_tx.metadata['cancels'] = tx.hash
            tx.replacement_hash = cancel_tx.hash
            tx.status = TransactionStatus.CANCELLED
            
            self._update_transaction_status(tx.hash, TransactionStatus.CANCELLED)
            
            logger.info(f"Transaction {tx_hash} cancelled: {cancel_tx.hash}")
            return cancel_tx
            
        except Exception as e:
            logger.error(f"Failed to cancel transaction: {e}")
            return None
    
    # ============ Batch Transactions ============
    
    def send_batch(
        self,
        transactions: List[Tuple[str, Union[float, int, str], Optional[str]]],
        options: Optional[TransactionOptions] = None,
        from_address: Optional[str] = None
    ) -> List[Transaction]:
        """
        Send a batch of transactions.
        
        Args:
            transactions: List of (to, value, data) tuples.
            options: Transaction options.
            from_address: Sender address.
            
        Returns:
            List of Transaction objects.
        """
        results = []
        nonce = None
        
        for i, (to, value, data) in enumerate(transactions):
            # Use nonce increment for each transaction
            if nonce is not None:
                options = (options or self.default_options)
                options.nonce = nonce + i
            else:
                options = options or self.default_options
            
            tx = self.send_transaction(
                to=to,
                value=value,
                data=data,
                options=options,
                from_address=from_address
            )
            
            # Update nonce for next transaction
            if i == 0:
                nonce = tx.nonce
            
            results.append(tx)
        
        return results
    
    # ============ Utility Methods ============
    
    def get_pending_count(self) -> int:
        """Get number of pending transactions."""
        with self._lock:
            return len(self._pending_transactions)
    
    def get_pending_transactions(self) -> List[Transaction]:
        """Get all pending transactions."""
        with self._lock:
            return list(self._pending_transactions.values())
    
    def get_transaction_history(self, limit: int = 50) -> List[Transaction]:
        """
        Get transaction history.
        
        Args:
            limit: Maximum number of transactions.
            
        Returns:
            List of Transaction objects.
        """
        with self._lock:
            return list(self._history)[-limit:]
    
    def get_transactions_by_address(
        self,
        address: str,
        limit: int = 50
    ) -> List[Transaction]:
        """
        Get transactions for a specific address.
        
        Args:
            address: Address to filter.
            limit: Maximum number of transactions.
            
        Returns:
            List of Transaction objects.
        """
        address = to_checksum_address(address)
        with self._lock:
            result = [
                tx for tx in self._history
                if tx.from_address.lower() == address.lower() or
                   tx.to_address.lower() == address.lower()
            ]
            return result[-limit:]
    
    def get_transaction_by_nonce(self, nonce: int) -> Optional[Transaction]:
        """
        Get transaction by nonce.
        
        Args:
            nonce: Transaction nonce.
            
        Returns:
            Transaction object or None.
        """
        with self._lock:
            for tx in self._history:
                if tx.nonce == nonce:
                    return tx
            return None
    
    def clear_history(self) -> None:
        """Clear transaction history."""
        with self._lock:
            self._history.clear()
    
    def stop_monitor(self) -> None:
        """Stop the pending transaction monitor."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Pending transaction monitor stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get transaction manager statistics."""
        with self._lock:
            total = len(self._transactions)
            pending = len(self._pending_transactions)
            confirmed = sum(1 for tx in self._transactions.values() if tx.status == TransactionStatus.CONFIRMED)
            failed = sum(1 for tx in self._transactions.values() if tx.status == TransactionStatus.FAILED)
            
            return {
                'total_transactions': total,
                'pending': pending,
                'confirmed': confirmed,
                'failed': failed,
                'history_length': len(self._history),
                'monitor_running': self._running
            }


def create_transaction_manager(
    web3_client: Any,
    gas_manager: Optional[GasManager] = None,
    default_options: Optional[TransactionOptions] = None
) -> Web3TransactionManager:
    """
    Create a transaction manager instance.
    
    Args:
        web3_client: Web3 client instance.
        gas_manager: Gas manager instance.
        default_options: Default transaction options.
        
    Returns:
        Web3TransactionManager instance.
    """
    return Web3TransactionManager(
        web3_client=web3_client,
        gas_manager=gas_manager,
        default_options=default_options
    )


__all__ = [
    'TransactionStatus',
    'TransactionType',
    'Transaction',
    'TransactionOptions',
    'Web3TransactionManager',
    'create_transaction_manager'
]
