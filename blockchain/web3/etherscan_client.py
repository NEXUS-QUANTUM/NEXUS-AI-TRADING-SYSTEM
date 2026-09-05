"""
Etherscan Client Module
========================

This module provides a client for interacting with the Etherscan API.
It supports various blockchain data queries including account balances,
transaction history, contract information, and gas price data.
"""

import time
import json
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.converters import to_int, to_float


class EtherscanClient:
    """
    Client for Etherscan API.
    
    Provides methods to fetch Ethereum blockchain data from Etherscan.
    Implements rate limiting and error handling.
    """
    
    BASE_URL = "https://api.etherscan.io/api"
    TESTNET_URL = "https://api-goerli.etherscan.io/api"
    
    def __init__(
        self,
        api_key: str,
        testnet: bool = False,
        timeout: int = 30,
        max_retries: int = 3,
        cache_ttl: int = 60
    ):
        """
        Initialize the Etherscan client.
        
        Args:
            api_key: Etherscan API key
            testnet: Use testnet (Goerli) instead of mainnet
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            cache_ttl: Cache TTL in seconds for API responses
        """
        self.api_key = api_key
        self.testnet = testnet
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_ttl = cache_ttl
        self.base_url = self.TESTNET_URL if testnet else self.BASE_URL
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_request_time = 0
        
        # Setup session with retry
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _rate_limit(self) -> None:
        """Apply rate limiting to respect Etherscan's API limits."""
        # Free tier: 5 calls per second
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.2:  # 200ms between calls
            time.sleep(0.2 - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(
        self,
        module: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        ignore_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Make an API request to Etherscan.
        
        Args:
            module: API module (e.g., 'account', 'contract', 'stats')
            action: API action (e.g., 'balance', 'txlist')
            params: Additional parameters
            ignore_cache: Ignore cached response
            
        Returns:
            API response as dictionary
            
        Raises:
            Exception: If API returns an error
        """
        # Build cache key
        cache_key = f"{module}:{action}:{json.dumps(params or {}, sort_keys=True)}"
        
        # Check cache
        if not ignore_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                return cached['data']
        
        # Build request parameters
        request_params = {
            'module': module,
            'action': action,
            'apikey': self.api_key
        }
        if params:
            request_params.update(params)
        
        # Rate limit
        self._rate_limit()
        
        # Make request
        try:
            response = self.session.get(
                self.base_url,
                params=request_params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if data.get('status') == '0':
                error_message = data.get('result', 'Unknown error')
                raise Exception(f"Etherscan API error: {error_message}")
            
            # Cache response
            self._cache[cache_key] = {
                'timestamp': time.time(),
                'data': data
            }
            
            return data
            
        except requests.RequestException as e:
            raise Exception(f"Request failed: {e}")
    
    # ============ Account Methods ============
    
    def get_account_balance(self, address: str) -> float:
        """
        Get the ETH balance for an address.
        
        Args:
            address: Ethereum address (0x...)
            
        Returns:
            Balance in ETH as float
        """
        data = self._make_request(
            module='account',
            action='balance',
            params={'address': address, 'tag': 'latest'}
        )
        wei = to_int(data.get('result', 0))
        return wei / 1e18
    
    def get_account_balance_multi(self, addresses: List[str]) -> Dict[str, float]:
        """
        Get ETH balances for multiple addresses.
        
        Args:
            addresses: List of Ethereum addresses
            
        Returns:
            Dictionary of address -> balance in ETH
        """
        if not addresses:
            return {}
        
        # Etherscan limits to 20 addresses per call
        addresses_str = ','.join(addresses[:20])
        data = self._make_request(
            module='account',
            action='balancemulti',
            params={'address': addresses_str, 'tag': 'latest'}
        )
        
        result = {}
        for item in data.get('result', []):
            address = item.get('account', '')
            wei = to_int(item.get('balance', 0))
            result[address] = wei / 1e18
        
        return result
    
    def get_transaction_history(
        self,
        address: str,
        start_block: int = 0,
        end_block: int = 99999999,
        sort: str = 'desc',
        page: int = 1,
        offset: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get transaction history for an address.
        
        Args:
            address: Ethereum address
            start_block: Starting block number
            end_block: Ending block number
            sort: Sort order ('asc' or 'desc')
            page: Page number for pagination
            offset: Number of results per page
            
        Returns:
            List of transaction dictionaries
        """
        data = self._make_request(
            module='account',
            action='txlist',
            params={
                'address': address,
                'startblock': start_block,
                'endblock': end_block,
                'sort': sort,
                'page': page,
                'offset': offset
            }
        )
        return data.get('result', [])
    
    def get_token_balance(self, address: str, contract_address: str) -> float:
        """
        Get the token balance for an address.
        
        Args:
            address: Wallet address
            contract_address: Token contract address
            
        Returns:
            Token balance as float (in token units)
        """
        data = self._make_request(
            module='account',
            action='tokenbalance',
            params={
                'address': address,
                'contractaddress': contract_address,
                'tag': 'latest'
            }
        )
        return to_float(data.get('result', 0))
    
    def get_token_transfers(
        self,
        address: str,
        contract_address: Optional[str] = None,
        start_block: int = 0,
        end_block: int = 99999999,
        sort: str = 'desc',
        page: int = 1,
        offset: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get token transfer history for an address.
        
        Args:
            address: Wallet address
            contract_address: Optional token contract address
            start_block: Starting block number
            end_block: Ending block number
            sort: Sort order ('asc' or 'desc')
            page: Page number
            offset: Results per page
            
        Returns:
            List of token transfer events
        """
        params = {
            'address': address,
            'startblock': start_block,
            'endblock': end_block,
            'sort': sort,
            'page': page,
            'offset': offset
        }
        if contract_address:
            params['contractaddress'] = contract_address
        
        data = self._make_request(
            module='account',
            action='tokentx',
            params=params
        )
        return data.get('result', [])
    
    # ============ Contract Methods ============
    
    def get_contract_abi(self, contract_address: str) -> List[Dict[str, Any]]:
        """
        Get the ABI for a verified contract.
        
        Args:
            contract_address: Contract address
            
        Returns:
            List of ABI entries
        """
        data = self._make_request(
            module='contract',
            action='getabi',
            params={'address': contract_address}
        )
        abi_str = data.get('result', '[]')
        return json.loads(abi_str)
    
    def get_contract_source_code(self, contract_address: str) -> Dict[str, Any]:
        """
        Get the source code for a verified contract.
        
        Args:
            contract_address: Contract address
            
        Returns:
            Contract source code information
        """
        data = self._make_request(
            module='contract',
            action='getsourcecode',
            params={'address': contract_address}
        )
        result = data.get('result', [])
        return result[0] if result else {}
    
    # ============ Token Methods ============
    
    def get_token_info(self, contract_address: str) -> Dict[str, Any]:
        """
        Get token information (name, symbol, decimals, total supply).
        
        Args:
            contract_address: Token contract address
            
        Returns:
            Token information dictionary
        """
        data = self._make_request(
            module='token',
            action='tokeninfo',
            params={'contractaddress': contract_address}
        )
        result = data.get('result', [])
        return result[0] if result else {}
    
    # ============ Stats Methods ============
    
    def get_eth_price(self) -> float:
        """
        Get current ETH price in USD.
        
        Returns:
            ETH price in USD
        """
        data = self._make_request(
            module='stats',
            action='ethprice'
        )
        result = data.get('result', {})
        return to_float(result.get('ethusd', 0))
    
    def get_eth_supply(self) -> float:
        """
        Get total ETH supply.
        
        Returns:
            Total supply in ETH
        """
        data = self._make_request(
            module='stats',
            action='ethsupply'
        )
        wei = to_int(data.get('result', 0))
        return wei / 1e18
    
    def get_gas_price(self) -> float:
        """
        Get current gas price in Gwei.
        
        Returns:
            Gas price in Gwei
        """
        data = self._make_request(
            module='gastracker',
            action='gasoracle'
        )
        result = data.get('result', {})
        return to_float(result.get('ProposeGasPrice', 0)) / 10
    
    # ============ Block Methods ============
    
    def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
        """
        Get block information by block number.
        
        Args:
            block_number: Block number
            
        Returns:
            Block data dictionary
        """
        data = self._make_request(
            module='proxy',
            action='eth_getBlockByNumber',
            params={
                'tag': hex(block_number),
                'boolean': 'true'
            }
        )
        return data.get('result', {})
    
    def get_latest_block_number(self) -> int:
        """
        Get the latest block number.
        
        Returns:
            Latest block number
        """
        data = self._make_request(
            module='proxy',
            action='eth_blockNumber'
        )
        hex_block = data.get('result', '0x0')
        return int(hex_block, 16)
    
    # ============ Utility Methods ============
    
    def parse_transaction(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a transaction dictionary into a more readable format.
        
        Args:
            tx: Raw transaction from Etherscan
            
        Returns:
            Parsed transaction
        """
        return {
            'hash': tx.get('hash', ''),
            'block_number': to_int(tx.get('blockNumber', 0)),
            'timestamp': datetime.fromtimestamp(to_int(tx.get('timeStamp', 0))),
            'from': tx.get('from', ''),
            'to': tx.get('to', ''),
            'value': to_int(tx.get('value', 0)) / 1e18,
            'gas_used': to_int(tx.get('gasUsed', 0)),
            'gas_price': to_int(tx.get('gasPrice', 0)) / 1e9,
            'transaction_index': to_int(tx.get('transactionIndex', 0)),
            'confirmations': to_int(tx.get('confirmations', 0))
        }
    
    def parse_token_transfer(self, transfer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a token transfer event.
        
        Args:
            transfer: Raw token transfer from Etherscan
            
        Returns:
            Parsed token transfer
        """
        return {
            'hash': transfer.get('hash', ''),
            'block_number': to_int(transfer.get('blockNumber', 0)),
            'timestamp': datetime.fromtimestamp(to_int(transfer.get('timeStamp', 0))),
            'from': transfer.get('from', ''),
            'to': transfer.get('to', ''),
            'contract_address': transfer.get('contractAddress', ''),
            'token_name': transfer.get('tokenName', ''),
            'token_symbol': transfer.get('tokenSymbol', ''),
            'token_decimals': to_int(transfer.get('tokenDecimal', 18)),
            'value': to_int(transfer.get('value', 0)) / (10 ** to_int(transfer.get('tokenDecimal', 18))),
            'gas_used': to_int(transfer.get('gasUsed', 0)),
            'gas_price': to_int(transfer.get('gasPrice', 0)) / 1e9
        }
    
    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._cache.clear()


def create_etherscan_client(config: Dict[str, Any]) -> EtherscanClient:
    """
    Create an Etherscan client from configuration.
    
    Args:
        config: Configuration dictionary with 'api_key' and optional 'testnet'
        
    Returns:
        EtherscanClient instance
    """
    return EtherscanClient(
        api_key=config.get('api_key', ''),
        testnet=config.get('testnet', False),
        timeout=config.get('timeout', 30),
        max_retries=config.get('max_retries', 3),
        cache_ttl=config.get('cache_ttl', 60)
    )


__all__ = [
    'EtherscanClient',
    'create_etherscan_client'
]
