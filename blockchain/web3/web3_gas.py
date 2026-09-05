"""
Web3 Gas Module
=================

This module provides gas management utilities for Web3 interactions.
It includes gas price estimation, gas limit calculation, EIP-1559 support,
and gas optimization strategies for Ethereum and EVM-compatible chains.
"""

import time
import logging
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from collections import deque

from web3 import Web3
from web3.types import TxParams, Wei, HexBytes
from web3.middleware import geth_poa_middleware
from eth_utils import to_wei, from_wei, to_checksum_address

from trading.bots.swing_bot.utils.cache import MemoryCache
from trading.bots.swing_bot.utils.validators import validate_data

logger = logging.getLogger(__name__)


@dataclass
class GasPriceInfo:
    """Gas price information."""
    timestamp: datetime
    slow: int          # Wei
    standard: int      # Wei
    fast: int          # Wei
    instant: int       # Wei
    base_fee: Optional[int] = None   # Wei (EIP-1559)
    max_priority_fee: Optional[int] = None  # Wei (EIP-1559)
    suggested_max_fee: Optional[int] = None  # Wei (EIP-1559)
    block_number: Optional[int] = None


@dataclass
class GasEstimate:
    """Gas estimate result."""
    gas_limit: int
    gas_price: int          # Wei
    max_fee_per_gas: Optional[int] = None  # Wei (EIP-1559)
    max_priority_fee_per_gas: Optional[int] = None  # Wei (EIP-1559)
    total_fee_wei: int
    total_fee_eth: float
    estimated_time_seconds: Optional[int] = None
    strategy: str = "standard"


@dataclass
class GasStrategy:
    """Gas strategy configuration."""
    name: str
    multiplier: float
    max_wait_seconds: int
    priority: str  # 'low', 'medium', 'high', 'urgent'


class GasManager:
    """
    Gas management for Ethereum transactions.
    
    Supports:
    - Gas price estimation (legacy and EIP-1559)
    - Gas limit estimation
    - Multiple strategies (slow, standard, fast, urgent)
    - Price caching and optimization
    - Historical price tracking
    """
    
    # Default gas strategies
    DEFAULT_STRATEGIES = {
        'slow': GasStrategy('slow', 0.8, 300, 'low'),
        'standard': GasStrategy('standard', 1.0, 120, 'medium'),
        'fast': GasStrategy('fast', 1.3, 60, 'high'),
        'urgent': GasStrategy('urgent', 1.8, 30, 'urgent'),
    }
    
    def __init__(
        self,
        web3_client: Any,
        default_strategy: str = 'standard',
        cache_ttl: int = 30,
        max_price_history: int = 100,
        gas_limit_multiplier: float = 1.1,
        priority_fee_buffer: float = 1.2
    ):
        """
        Initialize the gas manager.
        
        Args:
            web3_client: Web3 client instance.
            default_strategy: Default gas strategy name.
            cache_ttl: Cache TTL for gas prices in seconds.
            max_price_history: Maximum price history entries.
            gas_limit_multiplier: Multiplier for estimated gas limit.
            priority_fee_buffer: Buffer for priority fee (EIP-1559).
        """
        self.web3_client = web3_client
        self.default_strategy = default_strategy
        self.cache_ttl = cache_ttl
        self.max_price_history = max_price_history
        self.gas_limit_multiplier = gas_limit_multiplier
        self.priority_fee_buffer = priority_fee_buffer
        
        # Price history
        self._price_history: deque = deque(maxlen=max_price_history)
        
        # Cache
        self._cache = MemoryCache(max_size=100, default_ttl=cache_ttl)
        
        # Current gas price info
        self._current_info: Optional[GasPriceInfo] = None
        self._last_update: Optional[datetime] = None
        
        # Strategies
        self.strategies = self.DEFAULT_STRATEGIES.copy()
        
        logger.info("GasManager initialized")
    
    # ============ Price Estimation ============
    
    def get_gas_price_info(self, force_update: bool = False) -> GasPriceInfo:
        """
        Get current gas price information.
        
        Args:
            force_update: Force update from blockchain.
            
        Returns:
            GasPriceInfo object.
        """
        # Check cache
        if not force_update and self._current_info is not None:
            if self._last_update and (datetime.now() - self._last_update).total_seconds() < self.cache_ttl:
                return self._current_info
        
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        try:
            # Get current block
            block = w3.eth.get_block('pending')
            base_fee = block.get('baseFeePerGas')
            
            # Get current gas price (legacy)
            gas_price = w3.eth.gas_price
            
            # Get max priority fee (EIP-1559)
            max_priority_fee = None
            try:
                max_priority_fee = w3.eth.max_priority_fee
            except:
                # Fallback: use 1.5 Gwei as typical priority fee
                max_priority_fee = to_wei(1.5, 'gwei')
            
            # Calculate fees
            if base_fee is not None:
                # EIP-1559
                slow = base_fee + int(max_priority_fee * 0.8)
                standard = base_fee + int(max_priority_fee * 1.0)
                fast = base_fee + int(max_priority_fee * 1.5)
                instant = base_fee + int(max_priority_fee * 2.0)
                suggested_max_fee = base_fee + max_priority_fee
            else:
                # Legacy
                slow = int(gas_price * 0.9)
                standard = gas_price
                fast = int(gas_price * 1.2)
                instant = int(gas_price * 1.5)
                suggested_max_fee = None
            
            # Create info object
            info = GasPriceInfo(
                timestamp=datetime.now(),
                slow=slow,
                standard=standard,
                fast=fast,
                instant=instant,
                base_fee=base_fee,
                max_priority_fee=max_priority_fee,
                suggested_max_fee=suggested_max_fee,
                block_number=block.get('number')
            )
            
            # Update cache
            self._current_info = info
            self._last_update = datetime.now()
            self._price_history.append(info)
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get gas price info: {e}")
            # Return cached if available
            if self._current_info is not None:
                return self._current_info
            raise
    
    def get_gas_price_for_strategy(self, strategy: Optional[str] = None) -> int:
        """
        Get gas price for a specific strategy.
        
        Args:
            strategy: Strategy name (slow, standard, fast, urgent).
            
        Returns:
            Gas price in wei.
        """
        if strategy is None:
            strategy = self.default_strategy
        
        info = self.get_gas_price_info()
        
        strategy_map = {
            'slow': info.slow,
            'standard': info.standard,
            'fast': info.fast,
            'instant': info.instant,
        }
        
        return strategy_map.get(strategy, info.standard)
    
    def get_eip1559_fees(self, strategy: Optional[str] = None) -> Tuple[int, int]:
        """
        Get EIP-1559 fees (max fee and priority fee).
        
        Args:
            strategy: Strategy name.
            
        Returns:
            Tuple of (max_fee_per_gas, max_priority_fee_per_gas) in wei.
        """
        if strategy is None:
            strategy = self.default_strategy
        
        info = self.get_gas_price_info()
        
        if info.base_fee is None:
            # EIP-1559 not supported, fallback to legacy
            gas_price = self.get_gas_price_for_strategy(strategy)
            return gas_price, 0
        
        # Calculate max priority fee
        priority_map = {
            'slow': int(info.max_priority_fee * 0.8) if info.max_priority_fee else 0,
            'standard': int(info.max_priority_fee * 1.0) if info.max_priority_fee else 0,
            'fast': int(info.max_priority_fee * 1.5) if info.max_priority_fee else 0,
            'instant': int(info.max_priority_fee * 2.0) if info.max_priority_fee else 0,
        }
        priority_fee = priority_map.get(strategy, 0)
        
        # Calculate max fee
        max_fee = info.base_fee + priority_fee
        
        return max_fee, priority_fee
    
    # ============ Gas Limit Estimation ============
    
    def estimate_gas_limit(
        self,
        to: str,
        data: Optional[str] = None,
        value: Optional[int] = None,
        from_address: Optional[str] = None,
        contract_address: Optional[str] = None,
        function_name: Optional[str] = None,
        function_args: Optional[List] = None,
        **kwargs
    ) -> int:
        """
        Estimate gas limit for a transaction.
        
        Args:
            to: Recipient address.
            data: Transaction data.
            value: Transaction value in wei.
            from_address: Sender address.
            contract_address: Contract address for function call.
            function_name: Function name.
            function_args: Function arguments.
            **kwargs: Additional transaction parameters.
            
        Returns:
            Estimated gas limit.
        """
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        if from_address is None:
            if self.web3_client._account:
                from_address = self.web3_client._account.address
            else:
                from_address = '0x0000000000000000000000000000000000000000'
        
        # Build transaction
        tx: TxParams = {
            'from': from_address,
            'to': to,
            'value': value or 0,
        }
        
        if data:
            tx['data'] = data
        
        # If contract function call, encode it
        if contract_address and function_name:
            # Use contract object if available, else simple encoding
            try:
                contract = w3.eth.contract(
                    address=to_checksum_address(contract_address),
                    abi=kwargs.get('abi', [])
                )
                func = getattr(contract.functions, function_name)
                tx['to'] = to_checksum_address(contract_address)
                if function_args:
                    tx['data'] = func(*function_args).build_transaction(tx)['data']
                else:
                    tx['data'] = func().build_transaction(tx)['data']
            except:
                pass
        
        # Estimate gas
        try:
            gas_estimate = w3.eth.estimate_gas(tx)
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}")
            # Use default fallback
            gas_estimate = 21000 if not data else 100000
        
        # Apply multiplier
        return int(gas_estimate * self.gas_limit_multiplier)
    
    # ============ Transaction Preparation ============
    
    def prepare_transaction(
        self,
        to: str,
        value: Union[float, int, str] = 0,
        data: Optional[str] = None,
        from_address: Optional[str] = None,
        strategy: Optional[str] = None,
        gas_limit: Optional[int] = None,
        nonce: Optional[int] = None,
        contract_address: Optional[str] = None,
        function_name: Optional[str] = None,
        function_args: Optional[List] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Prepare a transaction with gas settings.
        
        Args:
            to: Recipient address.
            value: Value in ETH (float) or wei (int).
            data: Transaction data.
            from_address: Sender address.
            strategy: Gas strategy.
            gas_limit: Custom gas limit (auto-estimated if None).
            nonce: Transaction nonce (auto-fetched if None).
            contract_address: Contract address.
            function_name: Function name.
            function_args: Function arguments.
            **kwargs: Additional transaction parameters.
            
        Returns:
            Transaction dictionary ready for signing.
        """
        if strategy is None:
            strategy = self.default_strategy
        
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        if from_address is None:
            if self.web3_client._account:
                from_address = self.web3_client._account.address
            else:
                raise ValueError("No from address provided and no account set")
        
        # Convert value
        if isinstance(value, (float, int, str)):
            if isinstance(value, float) or (isinstance(value, str) and value.startswith('.')):
                value_wei = w3.to_wei(value, 'ether')
            else:
                value_wei = int(value)
        else:
            value_wei = 0
        
        # Build basic transaction
        tx: TxParams = {
            'from': from_address,
            'to': to,
            'value': value_wei,
            'nonce': nonce if nonce is not None else w3.eth.get_transaction_count(from_address),
        }
        
        if data:
            tx['data'] = data
        
        # Handle contract call
        if contract_address and function_name:
            try:
                contract = w3.eth.contract(
                    address=to_checksum_address(contract_address),
                    abi=kwargs.get('abi', [])
                )
                func = getattr(contract.functions, function_name)
                tx['to'] = to_checksum_address(contract_address)
                if function_args:
                    tx['data'] = func(*function_args).build_transaction(tx)['data']
                else:
                    tx['data'] = func().build_transaction(tx)['data']
            except Exception as e:
                logger.error(f"Contract function encoding failed: {e}")
                raise
        
        # Gas limit
        if gas_limit is None:
            tx['gas'] = self.estimate_gas_limit(
                to=tx['to'],
                data=tx.get('data'),
                value=tx['value'],
                from_address=from_address,
                contract_address=contract_address,
                function_name=function_name,
                function_args=function_args,
                **kwargs
            )
        else:
            tx['gas'] = gas_limit
        
        # Gas price (EIP-1559 or legacy)
        try:
            max_fee, priority_fee = self.get_eip1559_fees(strategy)
            if max_fee > 0 and priority_fee > 0:
                # Use EIP-1559
                tx['maxFeePerGas'] = max_fee
                tx['maxPriorityFeePerGas'] = priority_fee
                tx['type'] = '0x2'
            else:
                # Use legacy
                tx['gasPrice'] = self.get_gas_price_for_strategy(strategy)
        except:
            tx['gasPrice'] = self.get_gas_price_for_strategy(strategy)
        
        # Additional parameters
        if 'chain_id' in kwargs:
            tx['chainId'] = kwargs['chain_id']
        elif hasattr(w3.eth, 'chain_id'):
            tx['chainId'] = w3.eth.chain_id
        
        return dict(tx)
    
    # ============ Fee Calculation ============
    
    def calculate_fee(
        self,
        gas_limit: int,
        strategy: Optional[str] = None,
        include_priority: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate transaction fee.
        
        Args:
            gas_limit: Gas limit.
            strategy: Gas strategy.
            include_priority: Include priority fee in total.
            
        Returns:
            Fee information dictionary.
        """
        if strategy is None:
            strategy = self.default_strategy
        
        info = self.get_gas_price_info()
        gas_price = self.get_gas_price_for_strategy(strategy)
        
        # Calculate total fee
        total_wei = gas_limit * gas_price
        
        # EIP-1559 details
        max_fee, priority_fee = self.get_eip1559_fees(strategy)
        
        result = {
            'strategy': strategy,
            'gas_limit': gas_limit,
            'gas_price': gas_price,
            'total_fee_wei': total_wei,
            'total_fee_eth': total_wei / 1e18,
            'estimated_time_seconds': self._estimate_time(strategy),
        }
        
        if max_fee > 0:
            result['max_fee_per_gas'] = max_fee
            result['max_priority_fee_per_gas'] = priority_fee
            result['base_fee'] = info.base_fee
        
        return result
    
    def _estimate_time(self, strategy: str) -> Optional[int]:
        """
        Estimate transaction confirmation time.
        
        Args:
            strategy: Gas strategy.
            
        Returns:
            Estimated time in seconds.
        """
        strategy_obj = self.strategies.get(strategy)
        if strategy_obj:
            return strategy_obj.max_wait_seconds // 2
        return None
    
    # ============ Price History ============
    
    def get_price_history(self, limit: int = 10) -> List[GasPriceInfo]:
        """
        Get recent gas price history.
        
        Args:
            limit: Number of entries to return.
            
        Returns:
            List of GasPriceInfo objects.
        """
        return list(self._price_history)[-limit:]
    
    def get_average_price(self, strategy: str = 'standard', limit: int = 10) -> int:
        """
        Get average gas price over recent history.
        
        Args:
            strategy: Strategy name.
            limit: Number of entries to average.
            
        Returns:
            Average gas price in wei.
        """
        history = self.get_price_history(limit)
        if not history:
            return self.get_gas_price_for_strategy(strategy)
        
        strategy_map = {
            'slow': lambda x: x.slow,
            'standard': lambda x: x.standard,
            'fast': lambda x: x.fast,
            'instant': lambda x: x.instant,
        }
        getter = strategy_map.get(strategy, lambda x: x.standard)
        
        prices = [getter(info) for info in history]
        return int(sum(prices) / len(prices))
    
    def get_gas_price_percentile(self, percentile: float = 50) -> int:
        """
        Get gas price at a specific percentile from history.
        
        Args:
            percentile: Percentile (0-100).
            
        Returns:
            Gas price in wei.
        """
        history = self.get_price_history()
        if not history:
            return self.get_gas_price_info().standard
        
        prices = [info.standard for info in history]
        prices.sort()
        
        idx = int(len(prices) * percentile / 100)
        return prices[idx]
    
    # ============ Cache Management ============
    
    def clear_cache(self) -> None:
        """Clear the gas price cache."""
        self._cache.clear()
        self._current_info = None
        self._last_update = None
        logger.info("Gas price cache cleared")
    
    # ============ Utility Methods ============
    
    def is_eip1559_supported(self) -> bool:
        """
        Check if EIP-1559 is supported on the current network.
        
        Returns:
            True if EIP-1559 is supported.
        """
        info = self.get_gas_price_info()
        return info.base_fee is not None
    
    def to_wei(self, amount: Union[float, int, str], unit: str = 'ether') -> int:
        """Convert to wei."""
        return Web3.to_wei(amount, unit)
    
    def from_wei(self, amount: int, unit: str = 'ether') -> float:
        """Convert from wei."""
        return Web3.from_wei(amount, unit)


def create_gas_manager(
    web3_client: Any,
    default_strategy: str = 'standard',
    cache_ttl: int = 30,
    gas_limit_multiplier: float = 1.1
) -> GasManager:
    """
    Create a gas manager instance.
    
    Args:
        web3_client: Web3 client instance.
        default_strategy: Default gas strategy.
        cache_ttl: Cache TTL in seconds.
        gas_limit_multiplier: Gas limit multiplier.
        
    Returns:
        GasManager instance.
    """
    return GasManager(
        web3_client=web3_client,
        default_strategy=default_strategy,
        cache_ttl=cache_ttl,
        gas_limit_multiplier=gas_limit_multiplier
    )


__all__ = [
    'GasPriceInfo',
    'GasEstimate',
    'GasStrategy',
    'GasManager',
    'create_gas_manager'
]
