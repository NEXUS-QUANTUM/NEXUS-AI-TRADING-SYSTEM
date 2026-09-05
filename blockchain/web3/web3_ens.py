"""
Web3 ENS Module
==================

This module provides ENS (Ethereum Name Service) functionality for the Web3 client.
It supports name resolution, reverse resolution, and management of ENS names.
"""

import time
import logging
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache

from web3 import Web3
from web3.ens import ENS
from eth_utils import is_address, is_checksum_address, to_checksum_address

from trading.bots.swing_bot.utils.cache import MemoryCache
from trading.bots.swing_bot.utils.helpers import load_json, save_json
from trading.bots.swing_bot.utils.validators import validate_data

logger = logging.getLogger(__name__)


@dataclass
class ENSRecord:
    """ENS record data structure."""
    name: str
    address: str
    resolver: Optional[str] = None
    owner: Optional[str] = None
    ttl: int = 0
    expires_at: Optional[datetime] = None
    content_hash: Optional[str] = None
    text_records: Dict[str, str] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ENSReverseRecord:
    """Reverse ENS record."""
    address: str
    name: Optional[str] = None
    resolver: Optional[str] = None
    owner: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)


class ENSClient:
    """
    ENS client for resolving and managing ENS names.
    
    Provides methods for name resolution, reverse resolution,
    ownership lookup, and text record management.
    """
    
    # Default ENS registry addresses
    ENS_REGISTRY_MAINNET = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"
    ENS_REGISTRY_GOERLI = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"
    ENS_REGISTRY_SEPOLIA = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"
    
    # Common text record keys
    TEXT_RECORD_KEYS = [
        "description",
        "url",
        "avatar",
        "email",
        "com.github",
        "com.twitter",
        "com.discord",
        "com.telegram",
        "com.reddit",
        "org.telegram",
        "io.keybase",
    ]
    
    def __init__(
        self,
        web3_client: Any,
        registry_address: Optional[str] = None,
        cache_ttl: int = 300,
        enable_cache: bool = True
    ):
        """
        Initialize the ENS client.
        
        Args:
            web3_client: Web3 client instance.
            registry_address: ENS registry address (uses default if None).
            cache_ttl: Cache TTL in seconds for resolved names.
            enable_cache: Enable caching of resolved names.
        """
        self.web3_client = web3_client
        self.cache_ttl = cache_ttl
        self.enable_cache = enable_cache
        
        # Set registry address
        if registry_address is None:
            # Try to detect network
            try:
                chain_id = web3_client.chain_id
                if chain_id == 1:  # Mainnet
                    registry_address = self.ENS_REGISTRY_MAINNET
                elif chain_id == 5:  # Goerli
                    registry_address = self.ENS_REGISTRY_GOERLI
                elif chain_id == 11155111:  # Sepolia
                    registry_address = self.ENS_REGISTRY_SEPOLIA
                else:
                    registry_address = self.ENS_REGISTRY_MAINNET
            except:
                registry_address = self.ENS_REGISTRY_MAINNET
        
        self.registry_address = registry_address
        
        # Initialize ENS
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        self.ens = ENS.from_web3(w3, address=registry_address)
        
        # Cache for resolved names
        self._cache = MemoryCache(max_size=1000, default_ttl=cache_ttl) if enable_cache else None
        
        # Cache for reverse lookups
        self._reverse_cache = MemoryCache(max_size=500, default_ttl=cache_ttl) if enable_cache else None
        
        logger.info(f"ENS client initialized with registry: {registry_address}")
    
    # ============ Name Resolution ============
    
    def resolve(self, name: str, check_cache: bool = True) -> Optional[str]:
        """
        Resolve an ENS name to an Ethereum address.
        
        Args:
            name: ENS name (e.g., 'vitalik.eth').
            check_cache: Check cache before resolving.
            
        Returns:
            Ethereum address or None if not found.
        """
        if not name or '.' not in name:
            return None
        
        # Check cache
        if check_cache and self._cache is not None:
            cached = self._cache.get(name)
            if cached is not None:
                return cached
        
        try:
            address = self.ens.address(name)
            if address and is_address(address):
                address = to_checksum_address(address)
                # Cache result
                if self._cache is not None and address:
                    self._cache.set(name, address)
                return address
        except Exception as e:
            logger.debug(f"ENS resolution failed for {name}: {e}")
        
        return None
    
    def resolve_with_details(self, name: str) -> Optional[ENSRecord]:
        """
        Resolve an ENS name and return detailed information.
        
        Args:
            name: ENS name.
            
        Returns:
            ENSRecord object or None.
        """
        if not name or '.' not in name:
            return None
        
        try:
            # Get address
            address = self.ens.address(name)
            if not address or not is_address(address):
                return None
            
            address = to_checksum_address(address)
            
            # Get resolver
            resolver = self.ens.resolver(name)
            resolver_address = resolver.address if resolver else None
            
            # Get owner
            owner = self.ens.owner(name)
            
            # Get TTL
            ttl = self.ens.ttl(name) if hasattr(self.ens, 'ttl') else 0
            
            # Get content hash
            content_hash = None
            if resolver:
                try:
                    content_hash = resolver.content_hash(name)
                except:
                    pass
            
            # Get text records
            text_records = {}
            if resolver:
                for key in self.TEXT_RECORD_KEYS:
                    try:
                        value = resolver.text(name, key)
                        if value:
                            text_records[key] = value
                    except:
                        pass
            
            # Calculate expiry (if available)
            expires_at = None
            try:
                # This is a simplification - real expiry would require checking the registration
                pass
            except:
                pass
            
            record = ENSRecord(
                name=name,
                address=address,
                resolver=resolver_address,
                owner=owner,
                ttl=ttl,
                expires_at=expires_at,
                content_hash=content_hash,
                text_records=text_records,
                last_updated=datetime.now()
            )
            
            # Cache
            if self._cache is not None:
                self._cache.set(name, address)
                self._cache.set(f"{name}:details", record)
            
            return record
            
        except Exception as e:
            logger.debug(f"ENS resolution failed for {name}: {e}")
            return None
    
    # ============ Reverse Resolution ============
    
    def reverse_resolve(self, address: str, check_cache: bool = True) -> Optional[str]:
        """
        Resolve an Ethereum address to an ENS name (reverse lookup).
        
        Args:
            address: Ethereum address.
            check_cache: Check cache before resolving.
            
        Returns:
            ENS name or None.
        """
        if not address or not is_address(address):
            return None
        
        address = to_checksum_address(address)
        
        # Check cache
        if check_cache and self._reverse_cache is not None:
            cached = self._reverse_cache.get(address)
            if cached is not None:
                return cached
        
        try:
            name = self.ens.name(address)
            if name:
                # Cache result
                if self._reverse_cache is not None:
                    self._reverse_cache.set(address, name)
                return name
        except Exception as e:
            logger.debug(f"Reverse ENS resolution failed for {address}: {e}")
        
        return None
    
    def reverse_resolve_with_details(self, address: str) -> Optional[ENSReverseRecord]:
        """
        Resolve an address to ENS name with details.
        
        Args:
            address: Ethereum address.
            
        Returns:
            ENSReverseRecord object or None.
        """
        if not address or not is_address(address):
            return None
        
        address = to_checksum_address(address)
        
        try:
            name = self.ens.name(address)
            resolver = self.ens.resolver(name) if name else None
            owner = self.ens.owner(name) if name else None
            
            record = ENSReverseRecord(
                address=address,
                name=name,
                resolver=resolver.address if resolver else None,
                owner=owner,
                last_updated=datetime.now()
            )
            
            # Cache
            if self._reverse_cache is not None and name:
                self._reverse_cache.set(address, name)
            
            return record
            
        except Exception as e:
            logger.debug(f"Reverse ENS resolution failed for {address}: {e}")
            return None
    
    # ============ Ownership & Management ============
    
    def get_owner(self, name: str) -> Optional[str]:
        """
        Get the owner of an ENS name.
        
        Args:
            name: ENS name.
            
        Returns:
            Owner address or None.
        """
        if not name or '.' not in name:
            return None
        
        try:
            owner = self.ens.owner(name)
            return to_checksum_address(owner) if owner and is_address(owner) else None
        except Exception as e:
            logger.debug(f"Failed to get owner for {name}: {e}")
            return None
    
    def get_resolver(self, name: str) -> Optional[str]:
        """
        Get the resolver address for an ENS name.
        
        Args:
            name: ENS name.
            
        Returns:
            Resolver address or None.
        """
        if not name or '.' not in name:
            return None
        
        try:
            resolver = self.ens.resolver(name)
            return resolver.address if resolver else None
        except Exception as e:
            logger.debug(f"Failed to get resolver for {name}: {e}")
            return None
    
    def get_ttl(self, name: str) -> int:
        """
        Get the TTL for an ENS name.
        
        Args:
            name: ENS name.
            
        Returns:
            TTL in seconds.
        """
        if not name or '.' not in name:
            return 0
        
        try:
            return self.ens.ttl(name) if hasattr(self.ens, 'ttl') else 0
        except Exception as e:
            logger.debug(f"Failed to get TTL for {name}: {e}")
            return 0
    
    def get_text_record(self, name: str, key: str) -> Optional[str]:
        """
        Get a text record for an ENS name.
        
        Args:
            name: ENS name.
            key: Text record key.
            
        Returns:
            Text record value or None.
        """
        if not name or '.' not in name:
            return None
        
        try:
            resolver = self.ens.resolver(name)
            if resolver:
                value = resolver.text(name, key)
                return value
        except Exception as e:
            logger.debug(f"Failed to get text record {key} for {name}: {e}")
        
        return None
    
    def get_all_text_records(self, name: str) -> Dict[str, str]:
        """
        Get all text records for an ENS name.
        
        Args:
            name: ENS name.
            
        Returns:
            Dictionary of text records.
        """
        records = {}
        if not name or '.' not in name:
            return records
        
        for key in self.TEXT_RECORD_KEYS:
            value = self.get_text_record(name, key)
            if value is not None:
                records[key] = value
        
        return records
    
    def get_content_hash(self, name: str) -> Optional[str]:
        """
        Get the content hash for an ENS name.
        
        Args:
            name: ENS name.
            
        Returns:
            Content hash or None.
        """
        if not name or '.' not in name:
            return None
        
        try:
            resolver = self.ens.resolver(name)
            if resolver:
                return resolver.content_hash(name)
        except Exception as e:
            logger.debug(f"Failed to get content hash for {name}: {e}")
        
        return None
    
    # ============ Name Validation ============
    
    def is_valid_name(self, name: str) -> bool:
        """
        Check if a string is a valid ENS name.
        
        Args:
            name: String to check.
            
        Returns:
            True if valid ENS name, False otherwise.
        """
        if not name or '.' not in name:
            return False
        
        # Check length
        if len(name) > 255:
            return False
        
        # Check parts
        parts = name.split('.')
        if len(parts) < 2:
            return False
        
        # Check each part is valid
        for part in parts:
            if not part:
                return False
            # Check characters (simplified)
            if not all(c.isalnum() or c == '-' for c in part):
                return False
        
        return True
    
    def normalize_name(self, name: str) -> str:
        """
        Normalize an ENS name (convert to lower case).
        
        Args:
            name: ENS name.
            
        Returns:
            Normalized name.
        """
        if not name:
            return name
        
        # Basic normalization (ENS normalizes to lower case)
        return name.lower().strip()
    
    # ============ Cache Management ============
    
    def clear_cache(self) -> None:
        """Clear all cached ENS entries."""
        if self._cache is not None:
            self._cache.clear()
        if self._reverse_cache is not None:
            self._reverse_cache.clear()
        logger.info("ENS cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache sizes.
        """
        return {
            'name_cache_size': len(self._cache._cache) if self._cache else 0,
            'reverse_cache_size': len(self._reverse_cache._cache) if self._reverse_cache else 0,
        }
    
    # ============ Utility Methods ============
    
    def get_ens_info(self, name_or_address: str) -> Dict[str, Any]:
        """
        Get comprehensive ENS information.
        
        Args:
            name_or_address: ENS name or Ethereum address.
            
        Returns:
            Dictionary with ENS information.
        """
        result = {
            'input': name_or_address,
            'is_address': False,
            'is_name': False,
            'resolved_address': None,
            'resolved_name': None,
            'owner': None,
            'resolver': None,
            'ttl': 0,
            'text_records': {},
            'content_hash': None,
        }
        
        # Check if input is an address
        if is_address(name_or_address):
            address = to_checksum_address(name_or_address)
            result['is_address'] = True
            result['resolved_name'] = self.reverse_resolve(address)
            result['resolved_address'] = address
            
            # Get details if name found
            if result['resolved_name']:
                details = self.resolve_with_details(result['resolved_name'])
                if details:
                    result['owner'] = details.owner
                    result['resolver'] = details.resolver
                    result['ttl'] = details.ttl
                    result['text_records'] = details.text_records
                    result['content_hash'] = details.content_hash
        
        # Check if input is a name
        elif self.is_valid_name(name_or_address):
            name = self.normalize_name(name_or_address)
            result['is_name'] = True
            result['resolved_address'] = self.resolve(name)
            
            # Get details
            details = self.resolve_with_details(name)
            if details:
                result['owner'] = details.owner
                result['resolver'] = details.resolver
                result['ttl'] = details.ttl
                result['text_records'] = details.text_records
                result['content_hash'] = details.content_hash
        
        return result


def create_ens_client(
    web3_client: Any,
    registry_address: Optional[str] = None,
    cache_ttl: int = 300,
    enable_cache: bool = True
) -> ENSClient:
    """
    Create an ENS client.
    
    Args:
        web3_client: Web3 client instance.
        registry_address: ENS registry address.
        cache_ttl: Cache TTL in seconds.
        enable_cache: Enable caching.
        
    Returns:
        ENSClient instance.
    """
    return ENSClient(
        web3_client=web3_client,
        registry_address=registry_address,
        cache_ttl=cache_ttl,
        enable_cache=enable_cache
    )


def resolve_ens_name(
    web3_client: Any,
    name: str,
    cache_ttl: int = 300
) -> Optional[str]:
    """
    Convenience function to resolve an ENS name.
    
    Args:
        web3_client: Web3 client instance.
        name: ENS name.
        cache_ttl: Cache TTL.
        
    Returns:
        Ethereum address or None.
    """
    client = create_ens_client(web3_client, cache_ttl=cache_ttl)
    return client.resolve(name)


def reverse_resolve_address(
    web3_client: Any,
    address: str,
    cache_ttl: int = 300
) -> Optional[str]:
    """
    Convenience function to reverse resolve an address.
    
    Args:
        web3_client: Web3 client instance.
        address: Ethereum address.
        cache_ttl: Cache TTL.
        
    Returns:
        ENS name or None.
    """
    client = create_ens_client(web3_client, cache_ttl=cache_ttl)
    return client.reverse_resolve(address)


__all__ = [
    'ENSRecord',
    'ENSReverseRecord',
    'ENSClient',
    'create_ens_client',
    'resolve_ens_name',
    'reverse_resolve_address'
]
