"""
Web3 Configuration Module
===========================

This module provides configuration classes and utilities for Web3 clients.
It supports multiple blockchain networks, providers, and connection settings.
"""

import os
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class Web3ProviderConfig:
    """Configuration for a Web3 provider."""
    name: str
    url: str
    is_websocket: bool = False
    weight: int = 1
    timeout: int = 30
    max_retries: int = 3
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


@dataclass
class Web3NetworkConfig:
    """Configuration for a blockchain network."""
    name: str
    chain_id: int
    currency_symbol: str
    currency_decimals: int = 18
    gas_price_multiplier: float = 1.0
    providers: List[Web3ProviderConfig] = field(default_factory=list)
    explorer_url: Optional[str] = None
    rpc_urls: List[str] = field(default_factory=list)


@dataclass
class Web3Config:
    """Complete Web3 configuration."""
    default_network: str = "ethereum"
    networks: Dict[str, Web3NetworkConfig] = field(default_factory=dict)
    cache_ttl_seconds: int = 60
    max_cache_items: int = 1000
    request_timeout: int = 30
    max_retries: int = 3
    transaction_confirmation_blocks: int = 12
    gas_price_buffer_percent: float = 10.0


# Default network configurations
DEFAULT_NETWORKS = {
    "ethereum": Web3NetworkConfig(
        name="ethereum",
        chain_id=1,
        currency_symbol="ETH",
        currency_decimals=18,
        providers=[
            Web3ProviderConfig(
                name="infura",
                url="https://mainnet.infura.io/v3/",
                weight=10
            ),
            Web3ProviderConfig(
                name="alchemy",
                url="https://eth-mainnet.g.alchemy.com/v2/",
                weight=8
            ),
            Web3ProviderConfig(
                name="cloudflare",
                url="https://cloudflare-eth.com/",
                weight=5
            )
        ],
        explorer_url="https://etherscan.io/"
    ),
    "goerli": Web3NetworkConfig(
        name="goerli",
        chain_id=5,
        currency_symbol="ETH",
        currency_decimals=18,
        providers=[
            Web3ProviderConfig(
                name="infura",
                url="https://goerli.infura.io/v3/",
                weight=10
            ),
            Web3ProviderConfig(
                name="alchemy",
                url="https://eth-goerli.g.alchemy.com/v2/",
                weight=8
            )
        ],
        explorer_url="https://goerli.etherscan.io/"
    ),
    "sepolia": Web3NetworkConfig(
        name="sepolia",
        chain_id=11155111,
        currency_symbol="ETH",
        currency_decimals=18,
        providers=[
            Web3ProviderConfig(
                name="infura",
                url="https://sepolia.infura.io/v3/",
                weight=10
            ),
            Web3ProviderConfig(
                name="alchemy",
                url="https://eth-sepolia.g.alchemy.com/v2/",
                weight=8
            )
        ],
        explorer_url="https://sepolia.etherscan.io/"
    ),
    "polygon": Web3NetworkConfig(
        name="polygon",
        chain_id=137,
        currency_symbol="POL",
        currency_decimals=18,
        providers=[
            Web3ProviderConfig(
                name="infura",
                url="https://polygon-mainnet.infura.io/v3/",
                weight=10
            ),
            Web3ProviderConfig(
                name="alchemy",
                url="https://polygon-mainnet.g.alchemy.com/v2/",
                weight=8
            )
        ],
        explorer_url="https://polygonscan.com/"
    ),
    "arbitrum": Web3NetworkConfig(
        name="arbitrum",
        chain_id=42161,
        currency_symbol="ETH",
        currency_decimals=18,
        providers=[
            Web3ProviderConfig(
                name="infura",
                url="https://arbitrum-mainnet.infura.io/v3/",
                weight=10
            ),
            Web3ProviderConfig(
                name="alchemy",
                url="https://arb-mainnet.g.alchemy.com/v2/",
                weight=8
            )
        ],
        explorer_url="https://arbiscan.io/"
    ),
    "optimism": Web3NetworkConfig(
        name="optimism",
        chain_id=10,
        currency_symbol="ETH",
        currency_decimals=18,
        providers=[
            Web3ProviderConfig(
                name="infura",
                url="https://optimism-mainnet.infura.io/v3/",
                weight=10
            ),
            Web3ProviderConfig(
                name="alchemy",
                url="https://opt-mainnet.g.alchemy.com/v2/",
                weight=8
            )
        ],
        explorer_url="https://optimistic.etherscan.io/"
    ),
    "bnb": Web3NetworkConfig(
        name="bnb",
        chain_id=56,
        currency_symbol="BNB",
        currency_decimals=18,
        providers=[
            Web3ProviderConfig(
                name="binance",
                url="https://bsc-dataseed1.binance.org/",
                weight=10
            ),
            Web3ProviderConfig(
                name="binance2",
                url="https://bsc-dataseed2.binance.org/",
                weight=9
            ),
            Web3ProviderConfig(
                name="binance3",
                url="https://bsc-dataseed3.binance.org/",
                weight=8
            )
        ],
        explorer_url="https://bscscan.com/"
    ),
    "avalanche": Web3NetworkConfig(
        name="avalanche",
        chain_id=43114,
        currency_symbol="AVAX",
        currency_decimals=18,
        providers=[
            Web3ProviderConfig(
                name="avalanche",
                url="https://api.avax.network/ext/bc/C/rpc",
                weight=10
            ),
            Web3ProviderConfig(
                name="avalanche2",
                url="https://avalanche-c-chain.publicnode.com",
                weight=8
            )
        ],
        explorer_url="https://snowtrace.io/"
    ),
    "fantom": Web3NetworkConfig(
        name="fantom",
        chain_id=250,
        currency_symbol="FTM",
        currency_decimals=18,
        providers=[
            Web3ProviderConfig(
                name="fantom",
                url="https://rpcapi.fantom.network",
                weight=10
            ),
            Web3ProviderConfig(
                name="fantom2",
                url="https://rpc.ftm.tools",
                weight=8
            )
        ],
        explorer_url="https://ftmscan.com/"
    )
}


class Web3ConfigLoader:
    """
    Loader for Web3 configuration from various sources.
    """
    
    def __init__(self):
        self.config: Optional[Web3Config] = None
    
    def load_from_dict(self, config_dict: Dict[str, Any]) -> Web3Config:
        """
        Load configuration from a dictionary.
        
        Args:
            config_dict: Configuration dictionary.
            
        Returns:
            Web3Config instance.
        """
        networks = {}
        
        for network_name, network_config in config_dict.get('networks', {}).items():
            providers = []
            for provider_config in network_config.get('providers', []):
                providers.append(Web3ProviderConfig(
                    name=provider_config.get('name', ''),
                    url=provider_config.get('url', ''),
                    is_websocket=provider_config.get('is_websocket', False),
                    weight=provider_config.get('weight', 1),
                    timeout=provider_config.get('timeout', 30),
                    max_retries=provider_config.get('max_retries', 3),
                    api_key=provider_config.get('api_key'),
                    api_secret=provider_config.get('api_secret')
                ))
            
            networks[network_name] = Web3NetworkConfig(
                name=network_config.get('name', network_name),
                chain_id=network_config.get('chain_id', 1),
                currency_symbol=network_config.get('currency_symbol', 'ETH'),
                currency_decimals=network_config.get('currency_decimals', 18),
                gas_price_multiplier=network_config.get('gas_price_multiplier', 1.0),
                providers=providers,
                explorer_url=network_config.get('explorer_url'),
                rpc_urls=network_config.get('rpc_urls', [])
            )
        
        self.config = Web3Config(
            default_network=config_dict.get('default_network', 'ethereum'),
            networks=networks,
            cache_ttl_seconds=config_dict.get('cache_ttl_seconds', 60),
            max_cache_items=config_dict.get('max_cache_items', 1000),
            request_timeout=config_dict.get('request_timeout', 30),
            max_retries=config_dict.get('max_retries', 3),
            transaction_confirmation_blocks=config_dict.get('transaction_confirmation_blocks', 12),
            gas_price_buffer_percent=config_dict.get('gas_price_buffer_percent', 10.0)
        )
        
        return self.config
    
    def load_from_env(self) -> Web3Config:
        """
        Load configuration from environment variables.
        
        Returns:
            Web3Config instance.
        """
        config_dict = {
            'default_network': os.environ.get('WEB3_DEFAULT_NETWORK', 'ethereum'),
            'cache_ttl_seconds': int(os.environ.get('WEB3_CACHE_TTL', '60')),
            'max_cache_items': int(os.environ.get('WEB3_MAX_CACHE_ITEMS', '1000')),
            'request_timeout': int(os.environ.get('WEB3_REQUEST_TIMEOUT', '30')),
            'max_retries': int(os.environ.get('WEB3_MAX_RETRIES', '3')),
            'transaction_confirmation_blocks': int(os.environ.get('WEB3_CONFIRMATION_BLOCKS', '12')),
            'gas_price_buffer_percent': float(os.environ.get('WEB3_GAS_BUFFER', '10.0')),
            'networks': {}
        }
        
        # Load network configurations from environment
        for network_name in ['ethereum', 'goerli', 'sepolia', 'polygon', 'arbitrum', 'optimism', 'bnb', 'avalanche', 'fantom']:
            env_prefix = f"WEB3_{network_name.upper()}"
            
            # Check if network is enabled
            if os.environ.get(f"{env_prefix}_ENABLED", 'true').lower() == 'false':
                continue
            
            # Get chain ID
            chain_id_env = os.environ.get(f"{env_prefix}_CHAIN_ID")
            chain_id = int(chain_id_env) if chain_id_env else DEFAULT_NETWORKS.get(network_name, Web3NetworkConfig(name=network_name, chain_id=1)).chain_id
            
            # Get providers
            providers = []
            provider_urls = os.environ.get(f"{env_prefix}_PROVIDER_URLS", '')
            provider_names = os.environ.get(f"{env_prefix}_PROVIDER_NAMES", '')
            
            if provider_urls:
                urls = [u.strip() for u in provider_urls.split(',')]
                names = [n.strip() for n in provider_names.split(',')] if provider_names else [f"provider_{i}" for i in range(len(urls))]
                
                for i, (url, name) in enumerate(zip(urls, names)):
                    providers.append(Web3ProviderConfig(
                        name=name,
                        url=url,
                        is_websocket=url.startswith('wss://') or url.startswith('ws://'),
                        weight=10 - i,
                        timeout=int(os.environ.get(f"{env_prefix}_TIMEOUT", '30')),
                        max_retries=int(os.environ.get(f"{env_prefix}_MAX_RETRIES", '3')),
                        api_key=os.environ.get(f"{env_prefix}_API_KEY"),
                        api_secret=os.environ.get(f"{env_prefix}_API_SECRET")
                    ))
            else:
                # Use default providers
                default_network = DEFAULT_NETWORKS.get(network_name)
                if default_network:
                    providers = default_network.providers
        
            if providers:
                config_dict['networks'][network_name] = {
                    'name': network_name,
                    'chain_id': chain_id,
                    'currency_symbol': os.environ.get(f"{env_prefix}_CURRENCY", DEFAULT_NETWORKS.get(network_name, Web3NetworkConfig(name=network_name, chain_id=chain_id)).currency_symbol),
                    'providers': [p.__dict__ for p in providers],
                    'explorer_url': os.environ.get(f"{env_prefix}_EXPLORER_URL")
                }
        
        return self.load_from_dict(config_dict)
    
    def load_from_file(self, file_path: Union[str, Path]) -> Web3Config:
        """
        Load configuration from a file.
        
        Args:
            file_path: Path to configuration file (JSON or YAML).
            
        Returns:
            Web3Config instance.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            if file_path.suffix in ['.yaml', '.yml']:
                config_dict = yaml.safe_load(f)
            elif file_path.suffix == '.json':
                config_dict = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        return self.load_from_dict(config_dict)
    
    def load_default(self) -> Web3Config:
        """
        Load the default configuration.
        
        Returns:
            Web3Config instance.
        """
        self.config = Web3Config(
            default_network='ethereum',
            networks=DEFAULT_NETWORKS,
            cache_ttl_seconds=60,
            max_cache_items=1000,
            request_timeout=30,
            max_retries=3,
            transaction_confirmation_blocks=12,
            gas_price_buffer_percent=10.0
        )
        return self.config
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the configuration to a dictionary.
        
        Returns:
            Configuration dictionary.
        """
        if self.config is None:
            return {}
        
        return {
            'default_network': self.config.default_network,
            'networks': {
                name: {
                    'name': network.name,
                    'chain_id': network.chain_id,
                    'currency_symbol': network.currency_symbol,
                    'currency_decimals': network.currency_decimals,
                    'gas_price_multiplier': network.gas_price_multiplier,
                    'providers': [
                        {
                            'name': p.name,
                            'url': p.url,
                            'is_websocket': p.is_websocket,
                            'weight': p.weight,
                            'timeout': p.timeout,
                            'max_retries': p.max_retries
                        }
                        for p in network.providers
                    ],
                    'explorer_url': network.explorer_url,
                    'rpc_urls': network.rpc_urls
                }
                for name, network in self.config.networks.items()
            },
            'cache_ttl_seconds': self.config.cache_ttl_seconds,
            'max_cache_items': self.config.max_cache_items,
            'request_timeout': self.config.request_timeout,
            'max_retries': self.config.max_retries,
            'transaction_confirmation_blocks': self.config.transaction_confirmation_blocks,
            'gas_price_buffer_percent': self.config.gas_price_buffer_percent
        }


def get_web3_config(
    source: Optional[Union[str, Path, Dict[str, Any]]] = None
) -> Web3Config:
    """
    Get Web3 configuration from various sources.
    
    Args:
        source: Configuration source (file path, dict, or None for default).
        
    Returns:
        Web3Config instance.
    """
    loader = Web3ConfigLoader()
    
    if source is None:
        return loader.load_default()
    elif isinstance(source, dict):
        return loader.load_from_dict(source)
    elif isinstance(source, (str, Path)):
        return loader.load_from_file(source)
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")


def create_web3_config(
    default_network: str = 'ethereum',
    provider_urls: Optional[Dict[str, str]] = None,
    api_keys: Optional[Dict[str, str]] = None,
    **kwargs
) -> Web3Config:
    """
    Create a Web3 configuration from parameters.
    
    Args:
        default_network: Default network name.
        provider_urls: Dictionary of network -> provider URL.
        api_keys: Dictionary of network -> API key.
        **kwargs: Additional configuration parameters.
        
    Returns:
        Web3Config instance.
    """
    config_dict = {
        'default_network': default_network,
        'networks': {}
    }
    
    for network_name, url in (provider_urls or {}).items():
        providers = [{
            'name': 'custom',
            'url': url,
            'weight': 10
        }]
        
        # Add API key if provided
        if network_name in (api_keys or {}):
            providers[0]['api_key'] = api_keys[network_name]
        
        config_dict['networks'][network_name] = {
            'name': network_name,
            'providers': providers,
            'chain_id': kwargs.get(f'{network_name}_chain_id', 1),
            'currency_symbol': kwargs.get(f'{network_name}_currency', 'ETH')
        }
    
    # Add default networks if not specified
    if not config_dict['networks']:
        config_dict['networks'] = {
            name: {
                'name': name,
                'providers': [
                    {'name': 'default', 'url': 'https://' + name + '.example.com'}
                ]
            }
            for name in [default_network]
        }
    
    config_dict.update(kwargs)
    
    loader = Web3ConfigLoader()
    return loader.load_from_dict(config_dict)


__all__ = [
    'Web3ProviderConfig',
    'Web3NetworkConfig',
    'Web3Config',
    'Web3ConfigLoader',
    'get_web3_config',
    'create_web3_config',
    'DEFAULT_NETWORKS'
]
