"""
Web3 Token Module
===================

This module provides token management and interaction capabilities for ERC20,
ERC721, and ERC1155 tokens on Ethereum and EVM-compatible chains.

Supports:
- Token metadata (name, symbol, decimals, total supply)
- Balances and allowances
- Transfers and approvals
- Token detection and creation
- Batch operations via multicall
- Token event tracking
- Token price integration
- Caching and optimization
"""

import json
import logging
import time
from typing import Dict, List, Optional, Union, Any, Tuple, Set
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from functools import lru_cache
from collections import defaultdict

from web3 import Web3
from web3.types import BlockIdentifier, TxParams, Wei
from eth_utils import to_checksum_address

from trading.bots.swing_bot.utils.cache import MemoryCache
from trading.bots.swing_bot.utils.converters import to_int, to_float, to_str
from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.helpers import load_json, save_json

from .web3_multicall import Web3Multicall, create_multicall
from .web3_contract import Web3Contract, create_contract, create_erc20_contract, create_erc721_contract, create_erc1155_contract
from .web3_price import Web3Price, create_price_client

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token metadata."""
    address: str
    name: str
    symbol: str
    decimals: int
    total_supply: Optional[float] = None
    chain_id: Optional[int] = None
    token_type: str = "erc20"  # erc20, erc721, erc1155
    logo_uri: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    socials: Dict[str, str] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class TokenBalance:
    """Token balance information."""
    address: str
    token_address: str
    balance: float
    symbol: str
    decimals: int
    usd_value: Optional[float] = None
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class TokenAllowance:
    """Token allowance information."""
    token_address: str
    owner: str
    spender: str
    allowance: float
    decimals: int
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class TokenTransfer:
    """Token transfer event."""
    token_address: str
    from_address: str
    to_address: str
    value: float
    token_type: str
    token_id: Optional[int] = None
    transaction_hash: str
    block_number: int
    timestamp: datetime


class TokenManager:
    """
    Token manager for interacting with ERC20, ERC721, and ERC1155 tokens.
    
    Provides comprehensive token operations with caching, batch processing,
    and integration with price oracles.
    """
    
    def __init__(
        self,
        web3_client: Any,
        multicall: Optional[Web3Multicall] = None,
        price_client: Optional[Web3Price] = None,
        enable_cache: bool = True,
        cache_ttl: int = 300,
        max_cache_items: int = 1000
    ):
        """
        Initialize the token manager.
        
        Args:
            web3_client: Web3 client instance.
            multicall: Multicall client (auto-created if None).
            price_client: Price client (auto-created if None).
            enable_cache: Enable caching.
            cache_ttl: Cache TTL in seconds.
            max_cache_items: Maximum cache items.
        """
        self.web3_client = web3_client
        
        # Initialize multicall
        if multicall is None:
            self.multicall = create_multicall(web3_client)
        else:
            self.multicall = multicall
        
        # Initialize price client
        if price_client is None:
            self.price_client = create_price_client(web3_client)
        else:
            self.price_client = price_client
        
        # Cache
        self._cache = MemoryCache(max_size=max_cache_items, default_ttl=cache_ttl) if enable_cache else None
        
        # Token info cache (longer TTL)
        self._token_info_cache = MemoryCache(max_size=500, default_ttl=3600) if enable_cache else None
        
        # Known tokens (address -> TokenInfo)
        self._known_tokens: Dict[str, TokenInfo] = {}
        
        # Token contracts cache
        self._contract_cache: Dict[str, Web3Contract] = {}
        
        logger.info("TokenManager initialized")
    
    # ============ Token Creation ============
    
    def get_contract(self, address: str, token_type: str = 'erc20') -> Web3Contract:
        """
        Get or create a contract instance for a token.
        
        Args:
            address: Token contract address.
            token_type: Type of token ('erc20', 'erc721', 'erc1155').
            
        Returns:
            Web3Contract instance.
        """
        address = to_checksum_address(address)
        cache_key = f"{address}_{token_type}"
        
        if cache_key in self._contract_cache:
            return self._contract_cache[cache_key]
        
        if token_type == 'erc20':
            contract = create_erc20_contract(address, self.web3_client)
        elif token_type == 'erc721':
            contract = create_erc721_contract(address, self.web3_client)
        elif token_type == 'erc1155':
            contract = create_erc1155_contract(address, self.web3_client)
        else:
            raise ValueError(f"Unsupported token type: {token_type}")
        
        self._contract_cache[cache_key] = contract
        return contract
    
    def get_token_info(self, address: str, token_type: str = 'erc20') -> TokenInfo:
        """
        Get token information.
        
        Args:
            address: Token contract address.
            token_type: Type of token.
            
        Returns:
            TokenInfo object.
        """
        address = to_checksum_address(address)
        
        # Check cache
        cache_key = f"info_{address}_{token_type}"
        if self._token_info_cache is not None:
            cached = self._token_info_cache.get(cache_key)
            if cached is not None:
                return cached
        
        # Get contract
        contract = self.get_contract(address, token_type)
        
        try:
            name = contract.call('name')
        except:
            name = 'Unknown'
        
        try:
            symbol = contract.call('symbol')
        except:
            symbol = 'Unknown'
        
        decimals = 18
        total_supply = None
        
        if token_type == 'erc20':
            try:
                decimals = contract.call('decimals') or 18
            except:
                decimals = 18
            
            try:
                total_supply = contract.call('totalSupply')
                if total_supply is not None:
                    total_supply = total_supply / (10 ** decimals)
            except:
                total_supply = None
        
        info = TokenInfo(
            address=address,
            name=name,
            symbol=symbol,
            decimals=decimals,
            total_supply=total_supply,
            chain_id=self.web3_client.chain_id,
            token_type=token_type,
            last_updated=datetime.now()
        )
        
        # Cache
        if self._token_info_cache is not None:
            self._token_info_cache.set(cache_key, info)
        
        # Add to known tokens
        self._known_tokens[address] = info
        
        return info
    
    def get_token_balance(
        self,
        token_address: str,
        owner_address: str,
        token_type: str = 'erc20',
        token_id: Optional[int] = None
    ) -> float:
        """
        Get token balance for an address.
        
        Args:
            token_address: Token contract address.
            owner_address: Owner address.
            token_type: Type of token.
            token_id: Token ID for ERC721/ERC1155 (optional).
            
        Returns:
            Token balance.
        """
        token_address = to_checksum_address(token_address)
        owner_address = to_checksum_address(owner_address)
        
        if token_type == 'erc20':
            info = self.get_token_info(token_address, 'erc20')
            contract = self.get_contract(token_address, 'erc20')
            balance = contract.call('balanceOf', owner_address)
            return balance / (10 ** info.decimals) if balance else 0.0
            
        elif token_type == 'erc721':
            contract = self.get_contract(token_address, 'erc721')
            if token_id is not None:
                # Check specific token ownership
                owner = contract.call('ownerOf', token_id)
                return 1.0 if owner.lower() == owner_address.lower() else 0.0
            else:
                return float(contract.call('balanceOf', owner_address))
                
        elif token_type == 'erc1155':
            contract = self.get_contract(token_address, 'erc1155')
            if token_id is not None:
                balance = contract.call('balanceOf', owner_address, token_id)
                return float(balance)
            else:
                # For ERC1155, balanceOf requires a token ID
                return 0.0
                
        else:
            raise ValueError(f"Unsupported token type: {token_type}")
    
    def get_token_balances_batch(
        self,
        token_addresses: List[str],
        owner_address: str,
        token_type: str = 'erc20'
    ) -> Dict[str, float]:
        """
        Get balances for multiple tokens using multicall.
        
        Args:
            token_addresses: List of token addresses.
            owner_address: Owner address.
            token_type: Type of token.
            
        Returns:
            Dictionary of token_address -> balance.
        """
        if not token_addresses:
            return {}
        
        owner_address = to_checksum_address(owner_address)
        results = {}
        
        self.multicall.clear_calls()
        
        # Add calls for each token
        for token_address in token_addresses:
            token_address = to_checksum_address(token_address)
            
            if token_type == 'erc20':
                info = self.get_token_info(token_address, 'erc20')
                self.multicall.add_call(
                    token_address,
                    'balanceOf',
                    owner_address,
                    output_types=['uint256']
                )
            elif token_type == 'erc721':
                self.multicall.add_call(
                    token_address,
                    'balanceOf',
                    owner_address,
                    output_types=['uint256']
                )
            else:
                raise ValueError(f"Batch balances not supported for {token_type}")
        
        # Execute calls
        multicall_results = self.multicall.execute()
        
        # Process results
        for i, token_address in enumerate(token_addresses):
            result = multicall_results[i]
            if result.success and result.result is not None:
                if token_type == 'erc20':
                    info = self.get_token_info(token_address, 'erc20')
                    results[token_address] = result.result / (10 ** info.decimals)
                else:
                    results[token_address] = float(result.result)
            else:
                results[token_address] = 0.0
        
        return results
    
    def get_token_allowance(
        self,
        token_address: str,
        owner_address: str,
        spender_address: str
    ) -> float:
        """
        Get token allowance (ERC20 only).
        
        Args:
            token_address: Token contract address.
            owner_address: Owner address.
            spender_address: Spender address.
            
        Returns:
            Allowance amount.
        """
        token_address = to_checksum_address(token_address)
        owner_address = to_checksum_address(owner_address)
        spender_address = to_checksum_address(spender_address)
        
        info = self.get_token_info(token_address, 'erc20')
        contract = self.get_contract(token_address, 'erc20')
        allowance = contract.call('allowance', owner_address, spender_address)
        return allowance / (10 ** info.decimals) if allowance else 0.0
    
    # ============ Token Operations ============
    
    def approve(
        self,
        token_address: str,
        spender_address: str,
        amount: Union[float, int, str],
        from_address: Optional[str] = None,
        **tx_kwargs
    ) -> str:
        """
        Approve token spending (ERC20 only).
        
        Args:
            token_address: Token contract address.
            spender_address: Spender address.
            amount: Amount to approve (in token units).
            from_address: Sender address.
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        token_address = to_checksum_address(token_address)
        spender_address = to_checksum_address(spender_address)
        
        info = self.get_token_info(token_address, 'erc20')
        amount_wei = int(Decimal(str(amount)) * (10 ** info.decimals))
        
        contract = self.get_contract(token_address, 'erc20')
        return contract.send_transaction(
            'approve',
            spender_address,
            amount_wei,
            from_address=from_address,
            **tx_kwargs
        )
    
    def transfer(
        self,
        token_address: str,
        to_address: str,
        amount: Union[float, int, str],
        from_address: Optional[str] = None,
        **tx_kwargs
    ) -> str:
        """
        Transfer tokens (ERC20 only).
        
        Args:
            token_address: Token contract address.
            to_address: Recipient address.
            amount: Amount to transfer (in token units).
            from_address: Sender address.
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        token_address = to_checksum_address(token_address)
        to_address = to_checksum_address(to_address)
        
        info = self.get_token_info(token_address, 'erc20')
        amount_wei = int(Decimal(str(amount)) * (10 ** info.decimals))
        
        contract = self.get_contract(token_address, 'erc20')
        return contract.send_transaction(
            'transfer',
            to_address,
            amount_wei,
            from_address=from_address,
            **tx_kwargs
        )
    
    def transfer_from(
        self,
        token_address: str,
        from_address: str,
        to_address: str,
        amount: Union[float, int, str],
        **tx_kwargs
    ) -> str:
        """
        Transfer from another address (ERC20 only).
        
        Args:
            token_address: Token contract address.
            from_address: Sender address.
            to_address: Recipient address.
            amount: Amount to transfer (in token units).
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        token_address = to_checksum_address(token_address)
        from_address = to_checksum_address(from_address)
        to_address = to_checksum_address(to_address)
        
        info = self.get_token_info(token_address, 'erc20')
        amount_wei = int(Decimal(str(amount)) * (10 ** info.decimals))
        
        contract = self.get_contract(token_address, 'erc20')
        return contract.send_transaction(
            'transferFrom',
            from_address,
            to_address,
            amount_wei,
            **tx_kwargs
        )
    
    def transfer_nft(
        self,
        token_address: str,
        to_address: str,
        token_id: int,
        from_address: Optional[str] = None,
        **tx_kwargs
    ) -> str:
        """
        Transfer an NFT (ERC721 only).
        
        Args:
            token_address: Token contract address.
            to_address: Recipient address.
            token_id: Token ID.
            from_address: Sender address.
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        token_address = to_checksum_address(token_address)
        to_address = to_checksum_address(to_address)
        
        contract = self.get_contract(token_address, 'erc721')
        return contract.send_transaction(
            'transferFrom',
            from_address or self.web3_client.address,
            to_address,
            token_id,
            **tx_kwargs
        )
    
    def safe_transfer_nft(
        self,
        token_address: str,
        to_address: str,
        token_id: int,
        from_address: Optional[str] = None,
        **tx_kwargs
    ) -> str:
        """
        Safely transfer an NFT (ERC721 only).
        
        Args:
            token_address: Token contract address.
            to_address: Recipient address.
            token_id: Token ID.
            from_address: Sender address.
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        token_address = to_checksum_address(token_address)
        to_address = to_checksum_address(to_address)
        
        contract = self.get_contract(token_address, 'erc721')
        return contract.send_transaction(
            'safeTransferFrom',
            from_address or self.web3_client.address,
            to_address,
            token_id,
            **tx_kwargs
        )
    
    def transfer_erc1155(
        self,
        token_address: str,
        to_address: str,
        token_id: int,
        amount: int,
        from_address: Optional[str] = None,
        **tx_kwargs
    ) -> str:
        """
        Transfer ERC1155 tokens.
        
        Args:
            token_address: Token contract address.
            to_address: Recipient address.
            token_id: Token ID.
            amount: Amount to transfer.
            from_address: Sender address.
            **tx_kwargs: Additional transaction parameters.
            
        Returns:
            Transaction hash.
        """
        token_address = to_checksum_address(token_address)
        to_address = to_checksum_address(to_address)
        
        contract = self.get_contract(token_address, 'erc1155')
        return contract.send_transaction(
            'safeTransferFrom',
            from_address or self.web3_client.address,
            to_address,
            token_id,
            amount,
            b'',
            **tx_kwargs
        )
    
    # ============ Token Detection ============
    
    def detect_token_type(self, address: str) -> str:
        """
        Detect the type of token at an address.
        
        Args:
            address: Token contract address.
            
        Returns:
            Token type ('erc20', 'erc721', 'erc1155', or 'unknown').
        """
        address = to_checksum_address(address)
        
        # Try ERC20
        try:
            contract = self.get_contract(address, 'erc20')
            contract.call('name')
            contract.call('symbol')
            contract.call('decimals')
            return 'erc20'
        except:
            pass
        
        # Try ERC721
        try:
            contract = self.get_contract(address, 'erc721')
            contract.call('name')
            contract.call('symbol')
            contract.call('balanceOf', '0x0000000000000000000000000000000000000000')
            return 'erc721'
        except:
            pass
        
        # Try ERC1155
        try:
            contract = self.get_contract(address, 'erc1155')
            contract.call('uri', 0)
            return 'erc1155'
        except:
            pass
        
        return 'unknown'
    
    def is_erc20(self, address: str) -> bool:
        """Check if address is an ERC20 token."""
        return self.detect_token_type(address) == 'erc20'
    
    def is_erc721(self, address: str) -> bool:
        """Check if address is an ERC721 token."""
        return self.detect_token_type(address) == 'erc721'
    
    def is_erc1155(self, address: str) -> bool:
        """Check if address is an ERC1155 token."""
        return self.detect_token_type(address) == 'erc1155'
    
    # ============ Event Tracking ============
    
    def get_transfer_events(
        self,
        token_address: str,
        from_block: Union[int, str] = 'earliest',
        to_block: Union[int, str] = 'latest',
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        token_type: str = 'erc20',
        limit: Optional[int] = None
    ) -> List[TokenTransfer]:
        """
        Get transfer events for a token.
        
        Args:
            token_address: Token contract address.
            from_block: Starting block.
            to_block: Ending block.
            from_address: Filter by sender.
            to_address: Filter by receiver.
            token_type: Type of token.
            limit: Maximum number of events.
            
        Returns:
            List of TokenTransfer objects.
        """
        token_address = to_checksum_address(token_address)
        
        # Build event filters
        if token_type == 'erc20':
            event_name = 'Transfer'
            argument_filters = {}
            if from_address:
                argument_filters['from'] = to_checksum_address(from_address)
            if to_address:
                argument_filters['to'] = to_checksum_address(to_address)
            
            contract = self.get_contract(token_address, 'erc20')
            events = contract.get_events(
                event_name,
                from_block,
                to_block,
                argument_filters
            )
            
            info = self.get_token_info(token_address, 'erc20')
            
            transfers = []
            for event in events:
                if limit and len(transfers) >= limit:
                    break
                
                # Get timestamp from block (approximate)
                timestamp = datetime.fromtimestamp(time.time())
                try:
                    block = self.web3_client.get_block(event.block_number)
                    timestamp = datetime.fromtimestamp(block['timestamp'])
                except:
                    pass
                
                transfers.append(TokenTransfer(
                    token_address=token_address,
                    from_address=event.args.get('from', ''),
                    to_address=event.args.get('to', ''),
                    value=event.args.get('value', 0) / (10 ** info.decimals) if event.args.get('value') else 0,
                    token_type=token_type,
                    transaction_hash=event.transaction_hash,
                    block_number=event.block_number,
                    timestamp=timestamp
                ))
            
            return transfers
            
        elif token_type in ['erc721', 'erc1155']:
            # For ERC721/1155, we need to query Transfer events with tokenId
            contract = self.get_contract(token_address, token_type)
            events = contract.get_events('Transfer', from_block, to_block)
            
            transfers = []
            for event in events:
                if limit and len(transfers) >= limit:
                    break
                
                timestamp = datetime.fromtimestamp(time.time())
                try:
                    block = self.web3_client.get_block(event.block_number)
                    timestamp = datetime.fromtimestamp(block['timestamp'])
                except:
                    pass
                
                # For ERC721, Transfer event has from, to, tokenId
                args = event.args
                transfers.append(TokenTransfer(
                    token_address=token_address,
                    from_address=args.get('from', ''),
                    to_address=args.get('to', ''),
                    value=1.0,  # ERC721 transfers one token at a time
                    token_id=args.get('tokenId', 0),
                    token_type=token_type,
                    transaction_hash=event.transaction_hash,
                    block_number=event.block_number,
                    timestamp=timestamp
                ))
            
            return transfers
        
        else:
            raise ValueError(f"Unsupported token type: {token_type}")
    
    # ============ Price Integration ============
    
    def get_token_price(self, symbol: str) -> Optional[float]:
        """
        Get token price in USD.
        
        Args:
            symbol: Token symbol.
            
        Returns:
            Price in USD or None.
        """
        # Use price client
        price_data = self.price_client.fetch_price(f"{symbol.upper()}/USD")
        if price_data is not None:
            return price_data.price
        
        # Try with different format
        price_data = self.price_client.fetch_price(f"{symbol.upper()}/USDT")
        if price_data is not None:
            return price_data.price
        
        return None
    
    def get_token_usd_value(
        self,
        token_address: str,
        balance: Optional[float] = None,
        owner_address: Optional[str] = None
    ) -> Optional[float]:
        """
        Get USD value of token balance.
        
        Args:
            token_address: Token address.
            balance: Optional balance (fetched if not provided).
            owner_address: Owner address for balance fetch.
            
        Returns:
            USD value or None.
        """
        info = self.get_token_info(token_address)
        
        # Get balance if not provided
        if balance is None:
            if owner_address is None:
                raise ValueError("Either balance or owner_address must be provided")
            balance = self.get_token_balance(token_address, owner_address)
        
        if balance <= 0:
            return 0.0
        
        # Get price
        price = self.get_token_price(info.symbol)
        if price is not None:
            return balance * price
        
        return None
    
    # ============ Portfolio ============
    
    def get_portfolio(
        self,
        owner_address: str,
        token_addresses: List[str],
        include_usd: bool = True,
        include_nfts: bool = False
    ) -> Dict[str, TokenBalance]:
        """
        Get portfolio balances for multiple tokens.
        
        Args:
            owner_address: Owner address.
            token_addresses: List of token addresses.
            include_usd: Include USD values.
            include_nfts: Include NFT balances.
            
        Returns:
            Dictionary of token_address -> TokenBalance.
        """
        owner_address = to_checksum_address(owner_address)
        result = {}
        
        # Group by token type
        erc20_tokens = []
        erc721_tokens = []
        erc1155_tokens = []
        
        for addr in token_addresses:
            addr = to_checksum_address(addr)
            if include_nfts:
                token_type = self.detect_token_type(addr)
                if token_type == 'erc721':
                    erc721_tokens.append(addr)
                elif token_type == 'erc1155':
                    erc1155_tokens.append(addr)
                else:
                    erc20_tokens.append(addr)
            else:
                erc20_tokens.append(addr)
        
        # Get ERC20 balances
        if erc20_tokens:
            balances = self.get_token_balances_batch(erc20_tokens, owner_address, 'erc20')
            for addr, balance in balances.items():
                info = self.get_token_info(addr, 'erc20')
                usd_value = None
                if include_usd:
                    usd_value = self.get_token_usd_value(addr, balance)
                result[addr] = TokenBalance(
                    address=owner_address,
                    token_address=addr,
                    balance=balance,
                    symbol=info.symbol,
                    decimals=info.decimals,
                    usd_value=usd_value
                )
        
        # Get ERC721 balances
        if include_nfts and erc721_tokens:
            for addr in erc721_tokens:
                balance = self.get_token_balance(addr, owner_address, 'erc721')
                info = self.get_token_info(addr, 'erc721')
                result[addr] = TokenBalance(
                    address=owner_address,
                    token_address=addr,
                    balance=balance,
                    symbol=info.symbol,
                    decimals=0,
                    usd_value=None
                )
        
        # ERC1155 is more complex - we'd need specific token IDs
        # For now, we skip or provide a simple balance check
        
        return result
    
    # ============ Cache Management ============
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        if self._cache is not None:
            self._cache.clear()
        if self._token_info_cache is not None:
            self._token_info_cache.clear()
        self._contract_cache.clear()
        self._known_tokens.clear()
        logger.info("TokenManager caches cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'cache_size': len(self._cache._cache) if self._cache else 0,
            'token_info_cache_size': len(self._token_info_cache._cache) if self._token_info_cache else 0,
            'contract_cache_size': len(self._contract_cache),
            'known_tokens': len(self._known_tokens)
        }
    
    # ============ Utility Methods ============
    
    def get_token_logo(self, token_address: str) -> Optional[str]:
        """
        Get token logo URL.
        
        Args:
            token_address: Token address.
            
        Returns:
            Logo URL or None.
        """
        # This could integrate with token logos API (e.g., Trust Wallet, CoinGecko)
        # For now, return a placeholder
        try:
            import requests
            response = requests.get(
                f"https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/{token_address}/logo.png",
                timeout=5
            )
            if response.status_code == 200:
                return f"https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/{token_address}/logo.png"
        except:
            pass
        return None
    
    def get_token_display(
        self,
        token_address: str,
        amount: float,
        include_symbol: bool = True
    ) -> str:
        """
        Format token amount for display.
        
        Args:
            token_address: Token address.
            amount: Amount in token units.
            include_symbol: Include symbol in output.
            
        Returns:
            Formatted string.
        """
        info = self.get_token_info(token_address)
        formatted = f"{amount:,.{info.decimals}f}"
        if include_symbol:
            formatted += f" {info.symbol}"
        return formatted


def create_token_manager(
    web3_client: Any,
    enable_cache: bool = True,
    cache_ttl: int = 300
) -> TokenManager:
    """
    Create a token manager instance.
    
    Args:
        web3_client: Web3 client instance.
        enable_cache: Enable caching.
        cache_ttl: Cache TTL in seconds.
        
    Returns:
        TokenManager instance.
    """
    return TokenManager(
        web3_client=web3_client,
        enable_cache=enable_cache,
        cache_ttl=cache_ttl
    )


__all__ = [
    'TokenInfo',
    'TokenBalance',
    'TokenAllowance',
    'TokenTransfer',
    'TokenManager',
    'create_token_manager'
]
