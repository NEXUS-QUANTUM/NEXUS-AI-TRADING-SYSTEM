# blockchain/smart-contracts/erc721_contract.py
# NEXUS AI TRADING SYSTEM - ERC721 NFT Contract Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
ERC721 NFT Smart Contract Integration for NEXUS AI Trading System.
Provides comprehensive interaction with ERC721 compliant NFTs including:
- NFT ownership management
- Transfer operations (safe transfers)
- Approval management (single and all)
- Token metadata (URI)
- Royalty support (EIP-2981)
- Enumerable extensions
- Metadata management
- Batch operations
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware

# NEXUS Imports
from blockchain.smart_contracts.base_contract import BaseContract
from blockchain.smart_contracts.contract_abi import get_abi_dict
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.erc721")


# ============================================================================
# Enums & Constants
# ============================================================================

class ERC721Action(str, Enum):
    """ERC721 actions."""
    TRANSFER = "transfer"
    SAFE_TRANSFER = "safe_transfer"
    APPROVE = "approve"
    SET_APPROVAL_FOR_ALL = "set_approval_for_all"
    MINT = "mint"
    BURN = "burn"


@dataclass
class NFTMetadata:
    """NFT metadata structure."""
    name: str
    description: str
    image: str
    attributes: List[Dict[str, Any]]
    external_url: Optional[str] = None
    animation_url: Optional[str] = None
    youtube_url: Optional[str] = None
    background_color: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NFTInfo:
    """NFT information."""
    token_id: int
    owner: str
    uri: str
    metadata: Optional[NFTMetadata] = None
    created_at: Optional[datetime] = None
    transferred_at: Optional[datetime] = None
    royalty_info: Optional[Dict[str, Any]] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoyaltyInfo:
    """EIP-2981 Royalty information."""
    receiver: str
    royalty_fraction: int  # Basis points (e.g., 500 = 5%)
    royalty_amount: int  # In wei
    currency: str = "ETH"


@dataclass
class TransferEvent:
    """NFT transfer event."""
    token_id: int
    from_address: str
    to_address: str
    timestamp: datetime
    transaction_hash: str
    block_number: int


# ============================================================================
# ERC721 Contract Integration
# ============================================================================

class ERC721Contract(BaseContract):
    """
    ERC721 NFT Smart Contract Integration.
    Provides comprehensive interaction with ERC721 compliant NFTs.
    """

    # ERC721 ABI (minimal)
    ERC721_ABI = [
        # View Functions
        {
            "constant": True,
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "tokenId", "type": "uint256"}],
            "name": "ownerOf",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "tokenId", "type": "uint256"}],
            "name": "getApproved",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "operator", "type": "address"}
            ],
            "name": "isApprovedForAll",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "tokenId", "type": "uint256"}],
            "name": "tokenURI",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function"
        },
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

        # Write Functions
        {
            "constant": False,
            "inputs": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "tokenId", "type": "uint256"}
            ],
            "name": "transferFrom",
            "outputs": [],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "tokenId", "type": "uint256"}
            ],
            "name": "safeTransferFrom",
            "outputs": [],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "tokenId", "type": "uint256"}
            ],
            "name": "approve",
            "outputs": [],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "operator", "type": "address"},
                {"name": "approved", "type": "bool"}
            ],
            "name": "setApprovalForAll",
            "outputs": [],
            "type": "function"
        },

        # ERC721 Events
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "from", "type": "address"},
                {"indexed": True, "name": "to", "type": "address"},
                {"indexed": True, "name": "tokenId", "type": "uint256"}
            ],
            "name": "Transfer",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "owner", "type": "address"},
                {"indexed": True, "name": "approved", "type": "address"},
                {"indexed": True, "name": "tokenId", "type": "uint256"}
            ],
            "name": "Approval",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "owner", "type": "address"},
                {"indexed": True, "name": "operator", "type": "address"},
                {"indexed": False, "name": "approved", "type": "bool"}
            ],
            "name": "ApprovalForAll",
            "type": "event"
        },

        # EIP-2981 Royalty
        {
            "constant": True,
            "inputs": [
                {"name": "tokenId", "type": "uint256"},
                {"name": "salePrice", "type": "uint256"}
            ],
            "name": "royaltyInfo",
            "outputs": [
                {"name": "receiver", "type": "address"},
                {"name": "royaltyAmount", "type": "uint256"}
            ],
            "type": "function"
        },

        # ERC721 Enumerable (optional)
        {
            "constant": True,
            "inputs": [{"name": "index", "type": "uint256"}],
            "name": "tokenByIndex",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "index", "type": "uint256"}
            ],
            "name": "tokenOfOwnerByIndex",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
    ]

    def __init__(
        self,
        web3_client: Web3Client,
        contract_address: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ERC721 contract integration.

        Args:
            web3_client: Web3 client instance
            contract_address: ERC721 contract address
            config: Configuration dictionary
        """
        super().__init__(
            web3_client=web3_client,
            contract_name="ERC721",
            contract_address=contract_address or "",
            abi=self.ERC721_ABI,
            config=config,
        )

        # NFT cache
        self._nft_cache: Dict[int, NFTInfo] = {}
        self._owner_nft_cache: Dict[str, List[int]] = {}

        # Metadata resolver
        self._metadata_resolver = self._create_metadata_resolver()

        logger.info(
            "ERC721Contract initialized",
            extra={
                "contract_address": self.contract_address,
                "chain": web3_client.chain_name,
            }
        )

    # -----------------------------------------------------------------------
    # Token Information
    # -----------------------------------------------------------------------

    async def get_name(self) -> Optional[str]:
        """Get collection name."""
        try:
            name = await self._call_contract_function("name")
            return name
        except Exception:
            return None

    async def get_symbol(self) -> Optional[str]:
        """Get collection symbol."""
        try:
            symbol = await self._call_contract_function("symbol")
            return symbol
        except Exception:
            return None

    async def get_token_uri(
        self,
        token_id: int,
    ) -> Optional[str]:
        """
        Get token URI.

        Args:
            token_id: Token ID

        Returns:
            Token URI or None
        """
        try:
            uri = await self._call_contract_function("tokenURI", token_id)
            return uri
        except Exception:
            return None

    async def get_token_info(
        self,
        token_id: int,
        force_refresh: bool = False,
    ) -> Optional[NFTInfo]:
        """
        Get NFT information.

        Args:
            token_id: Token ID
            force_refresh: Force refresh cache

        Returns:
            NFTInfo or None
        """
        if not force_refresh and token_id in self._nft_cache:
            return self._nft_cache[token_id]

        try:
            # Get owner
            owner = await self.owner_of(token_id)
            if not owner:
                return None

            # Get URI
            uri = await self.get_token_uri(token_id)

            # Get metadata
            metadata = await self._fetch_metadata(uri) if uri else None

            # Get royalty info
            royalty_info = await self.get_royalty_info(token_id)

            nft_info = NFTInfo(
                token_id=token_id,
                owner=owner,
                uri=uri or "",
                metadata=metadata,
                created_at=datetime.utcnow(),
                royalty_info=royalty_info,
            )

            self._nft_cache[token_id] = nft_info
            return nft_info

        except Exception as e:
            logger.error(f"Error getting token info for {token_id}: {e}")
            return None

    async def get_metadata(
        self,
        token_id: int,
    ) -> Optional[NFTMetadata]:
        """
        Get NFT metadata.

        Args:
            token_id: Token ID

        Returns:
            NFTMetadata or None
        """
        token_info = await self.get_token_info(token_id)
        return token_info.metadata if token_info else None

    # -----------------------------------------------------------------------
    # Ownership Queries
    # -----------------------------------------------------------------------

    async def owner_of(
        self,
        token_id: int,
    ) -> Optional[str]:
        """
        Get owner of an NFT.

        Args:
            token_id: Token ID

        Returns:
            Owner address or None
        """
        try:
            owner = await self._call_contract_function("ownerOf", token_id)
            return owner
        except Exception:
            return None

    async def balance_of(
        self,
        owner: Union[str, Address],
    ) -> int:
        """
        Get NFT balance of an account.

        Args:
            owner: Owner address

        Returns:
            Number of NFTs owned
        """
        owner = Web3.to_checksum_address(owner)

        try:
            balance = await self._call_contract_function("balanceOf", owner)
            return int(balance) if balance else 0
        except Exception:
            return 0

    async def tokens_of_owner(
        self,
        owner: Union[str, Address],
        limit: Optional[int] = None,
    ) -> List[int]:
        """
        Get tokens owned by an account.

        Args:
            owner: Owner address
            limit: Maximum number of tokens to return

        Returns:
            List of token IDs
        """
        owner = Web3.to_checksum_address(owner)

        # Check cache
        if owner in self._owner_nft_cache:
            tokens = self._owner_nft_cache[owner]
            if limit:
                return tokens[:limit]
            return tokens

        tokens = []

        try:
            # Try using enumerable extension
            total = await self.balance_of(owner)

            for i in range(min(total, 1000)):  # Limit to 1000 tokens
                try:
                    token_id = await self._call_contract_function(
                        "tokenOfOwnerByIndex",
                        owner,
                        i,
                    )
                    if token_id:
                        tokens.append(int(token_id))
                except Exception:
                    continue

            if not tokens:
                # Fallback to scanning events
                tokens = await self._get_tokens_from_events(owner)

        except Exception as e:
            logger.error(f"Error getting tokens of owner: {e}")

        self._owner_nft_cache[owner] = tokens
        return tokens[:limit] if limit else tokens

    async def _get_tokens_from_events(
        self,
        owner: str,
    ) -> List[int]:
        """Get tokens from Transfer events."""
        # Would query events from blockchain
        # This is a placeholder
        return []

    # -----------------------------------------------------------------------
    # Transfer Operations
    # -----------------------------------------------------------------------

    async def transfer_from(
        self,
        from_address: Union[str, Address],
        to_address: Union[str, Address],
        token_id: int,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Transfer NFT from one address to another.

        Args:
            from_address: From address
            to_address: To address
            token_id: Token ID
            sender: Sender address (optional)

        Returns:
            Transaction hash or None
        """
        from_address = Web3.to_checksum_address(from_address)
        to_address = Web3.to_checksum_address(to_address)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        try:
            tx = await self._build_transaction(
                "transferFrom",
                from_address,
                to_address,
                token_id,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                logger.info(
                    f"Transfer successful",
                    extra={
                        "from": from_address,
                        "to": to_address,
                        "token_id": token_id,
                        "tx_hash": tx_hash,
                    }
                )

                # Clear cache
                self._nft_cache.pop(token_id, None)
                self._owner_nft_cache.pop(from_address, None)
                self._owner_nft_cache.pop(to_address, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error transferring: {e}")
            return None

    async def safe_transfer_from(
        self,
        from_address: Union[str, Address],
        to_address: Union[str, Address],
        token_id: int,
        data: Optional[bytes] = None,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Safely transfer NFT (with ERC721Receiver check).

        Args:
            from_address: From address
            to_address: To address
            token_id: Token ID
            data: Additional data
            sender: Sender address (optional)

        Returns:
            Transaction hash or None
        """
        from_address = Web3.to_checksum_address(from_address)
        to_address = Web3.to_checksum_address(to_address)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        try:
            tx = await self._build_transaction(
                "safeTransferFrom",
                from_address,
                to_address,
                token_id,
                data or b"",
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                logger.info(
                    f"Safe transfer successful",
                    extra={
                        "from": from_address,
                        "to": to_address,
                        "token_id": token_id,
                        "tx_hash": tx_hash,
                    }
                )

                # Clear cache
                self._nft_cache.pop(token_id, None)
                self._owner_nft_cache.pop(from_address, None)
                self._owner_nft_cache.pop(to_address, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error safe transferring: {e}")
            return None

    # -----------------------------------------------------------------------
    # Approval Operations
    # -----------------------------------------------------------------------

    async def approve(
        self,
        to_address: Union[str, Address],
        token_id: int,
        owner: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Approve an address to transfer a specific NFT.

        Args:
            to_address: Address to approve
            token_id: Token ID
            owner: Owner address (optional)

        Returns:
            Transaction hash or None
        """
        to_address = Web3.to_checksum_address(to_address)
        owner = Web3.to_checksum_address(owner or self.web3_client.default_account)

        try:
            tx = await self._build_transaction(
                "approve",
                to_address,
                token_id,
            )

            tx_hash = await self._send_transaction(tx, owner)

            if tx_hash:
                logger.info(
                    f"Approval successful",
                    extra={
                        "to": to_address,
                        "token_id": token_id,
                        "owner": owner,
                        "tx_hash": tx_hash,
                    }
                )

                # Clear cache
                self._nft_cache.pop(token_id, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error approving: {e}")
            return None

    async def set_approval_for_all(
        self,
        operator: Union[str, Address],
        approved: bool,
        owner: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Set approval for all NFTs of an account.

        Args:
            operator: Operator address
            approved: Approval status
            owner: Owner address (optional)

        Returns:
            Transaction hash or None
        """
        operator = Web3.to_checksum_address(operator)
        owner = Web3.to_checksum_address(owner or self.web3_client.default_account)

        try:
            tx = await self._build_transaction(
                "setApprovalForAll",
                operator,
                approved,
            )

            tx_hash = await self._send_transaction(tx, owner)

            if tx_hash:
                logger.info(
                    f"Set approval for all successful",
                    extra={
                        "operator": operator,
                        "approved": approved,
                        "owner": owner,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error setting approval for all: {e}")
            return None

    async def get_approved(
        self,
        token_id: int,
    ) -> Optional[str]:
        """
        Get approved address for an NFT.

        Args:
            token_id: Token ID

        Returns:
            Approved address or None
        """
        try:
            approved = await self._call_contract_function("getApproved", token_id)
            return approved
        except Exception:
            return None

    async def is_approved_for_all(
        self,
        owner: Union[str, Address],
        operator: Union[str, Address],
    ) -> bool:
        """
        Check if operator is approved for all NFTs of owner.

        Args:
            owner: Owner address
            operator: Operator address

        Returns:
            Approval status
        """
        owner = Web3.to_checksum_address(owner)
        operator = Web3.to_checksum_address(operator)

        try:
            approved = await self._call_contract_function(
                "isApprovedForAll",
                owner,
                operator,
            )
            return bool(approved) if approved is not None else False
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Royalty Operations (EIP-2981)
    # -----------------------------------------------------------------------

    async def get_royalty_info(
        self,
        token_id: int,
        sale_price: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get royalty information for an NFT.

        Args:
            token_id: Token ID
            sale_price: Sale price in wei (optional)

        Returns:
            Royalty info or None
        """
        try:
            if not self._has_function("royaltyInfo"):
                return None

            sale_price = sale_price or 0
            receiver, amount = await self._call_contract_function(
                "royaltyInfo",
                token_id,
                sale_price,
            )

            if receiver and amount:
                return {
                    "receiver": receiver,
                    "royalty_amount": int(amount) if amount else 0,
                    "sale_price": sale_price,
                    "royalty_fraction": (int(amount) / sale_price) if sale_price > 0 else 0,
                }

            return None

        except Exception as e:
            logger.error(f"Error getting royalty info: {e}")
            return None

    async def get_royalty_receiver(
        self,
        token_id: int,
    ) -> Optional[str]:
        """Get royalty receiver address."""
        info = await self.get_royalty_info(token_id)
        return info.get("receiver") if info else None

    async def get_royalty_amount(
        self,
        token_id: int,
        sale_price: int,
    ) -> int:
        """Get royalty amount for a sale price."""
        info = await self.get_royalty_info(token_id, sale_price)
        return info.get("royalty_amount", 0) if info else 0

    # -----------------------------------------------------------------------
    # Metadata Resolution
    # -----------------------------------------------------------------------

    async def _fetch_metadata(
        self,
        uri: str,
    ) -> Optional[NFTMetadata]:
        """
        Fetch metadata from URI.

        Args:
            uri: Metadata URI

        Returns:
            NFTMetadata or None
        """
        try:
            if uri.startswith("ipfs://"):
                # Would use IPFS gateway
                return None
            elif uri.startswith("http"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(uri, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            return self._parse_metadata(data)
            return None

        except Exception as e:
            logger.error(f"Error fetching metadata: {e}")
            return None

    def _parse_metadata(self, data: Dict[str, Any]) -> NFTMetadata:
        """Parse metadata JSON."""
        return NFTMetadata(
            name=data.get("name", ""),
            description=data.get("description", ""),
            image=data.get("image", ""),
            attributes=data.get("attributes", []),
            external_url=data.get("external_url"),
            animation_url=data.get("animation_url"),
            youtube_url=data.get("youtube_url"),
            background_color=data.get("background_color"),
            properties=data.get("properties", {}),
            metadata=data,
        )

    def _create_metadata_resolver(self) -> Dict[str, Any]:
        """Create metadata resolver."""
        return {
            "ipfs": self._resolve_ipfs,
            "http": self._resolve_http,
        }

    async def _resolve_ipfs(self, uri: str) -> Optional[Dict[str, Any]]:
        """Resolve IPFS URI."""
        # Would use IPFS gateway
        return None

    async def _resolve_http(self, uri: str) -> Optional[Dict[str, Any]]:
        """Resolve HTTP URI."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(uri, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

    # -----------------------------------------------------------------------
    # Batch Operations
    # -----------------------------------------------------------------------

    async def transfer_batch(
        self,
        from_address: Union[str, Address],
        to_address: Union[str, Address],
        token_ids: List[int],
        sender: Optional[Union[str, Address]] = None,
    ) -> List[Optional[str]]:
        """
        Transfer multiple NFTs.

        Args:
            from_address: From address
            to_address: To address
            token_ids: List of token IDs
            sender: Sender address (optional)

        Returns:
            List of transaction hashes
        """
        tx_hashes = []

        for token_id in token_ids:
            tx_hash = await self.transfer_from(
                from_address,
                to_address,
                token_id,
                sender,
            )
            tx_hashes.append(tx_hash)

        return tx_hashes

    # -----------------------------------------------------------------------
    # Event Monitoring
    # -----------------------------------------------------------------------

    async def get_transfer_events(
        self,
        token_id: Optional[int] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ) -> List[TransferEvent]:
        """
        Get transfer events.

        Args:
            token_id: Filter by token ID
            from_block: From block number
            to_block: To block number

        Returns:
            List of TransferEvent
        """
        events = []

        try:
            # Would query events from blockchain
            # This is a placeholder implementation
            return events

        except Exception as e:
            logger.error(f"Error getting transfer events: {e}")
            return events

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def _has_function(self, function_name: str) -> bool:
        """Check if contract has a function."""
        for item in self.abi:
            if item.get("type") == "function" and item.get("name") == function_name:
                return True
        return False

    def is_erc721(self) -> bool:
        """Check if contract is ERC721 compliant."""
        required_functions = [
            "balanceOf",
            "ownerOf",
            "safeTransferFrom",
            "transferFrom",
            "approve",
            "setApprovalForAll",
            "getApproved",
            "isApprovedForAll",
        ]
        return all(self._has_function(f) for f in required_functions)

    def is_enumerable(self) -> bool:
        """Check if contract implements enumerable extension."""
        return self._has_function("tokenByIndex") and self._has_function("tokenOfOwnerByIndex")

    def supports_royalties(self) -> bool:
        """Check if contract supports EIP-2981 royalties."""
        return self._has_function("royaltyInfo")

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._nft_cache.clear()
        self._owner_nft_cache.clear()

    # -----------------------------------------------------------------------
    # Transaction Building
    # -----------------------------------------------------------------------

    async def _build_transaction(
        self,
        function_name: str,
        *args,
    ) -> Dict[str, Any]:
        """Build a transaction."""
        try:
            func = getattr(self.contract.functions, function_name)
            tx = func(*args).build_transaction({
                "from": self.web3_client.default_account,
                "nonce": await self.web3_client.get_nonce(self.web3_client.default_account),
                "gas": 0,
                "gasPrice": await self.web3_client.get_gas_price(),
            })

            # Estimate gas
            gas = await self._estimate_gas(function_name, *args)
            tx["gas"] = int(gas * 1.3)

            return tx

        except Exception as e:
            logger.error(f"Error building transaction: {e}")
            raise

    async def _estimate_gas(
        self,
        function_name: str,
        *args,
    ) -> int:
        """Estimate gas for a transaction."""
        try:
            func = getattr(self.contract.functions, function_name)
            gas = await self.web3_client.estimate_gas(
                func(*args).build_transaction({
                    "from": self.web3_client.default_account,
                })
            )
            return int(gas)
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}, using default")
            return 150000

    async def _send_transaction(
        self,
        tx: Dict[str, Any],
        from_address: str,
    ) -> Optional[str]:
        """Send a transaction."""
        try:
            signed_tx = self.web3_client.sign_transaction(tx, from_address)
            tx_hash = await self.web3_client.send_raw_transaction(signed_tx.rawTransaction)

            receipt = await self.web3_client.wait_for_transaction_receipt(tx_hash)

            if receipt and receipt.get("status", 0) == 1:
                return Web3.to_hex(tx_hash)
            else:
                logger.error(f"Transaction failed: {tx_hash}")
                return None

        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            return None

    # -----------------------------------------------------------------------
    # Performance Metrics
    # -----------------------------------------------------------------------

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            "nft_cache_size": len(self._nft_cache),
            "owner_nft_cache_size": len(self._owner_nft_cache),
            "is_erc721": self.is_erc721(),
            "is_enumerable": self.is_enumerable(),
            "supports_royalties": self.supports_royalties(),
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_erc721_contract(
    web3_client: Web3Client,
    contract_address: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ERC721Contract:
    """
    Factory function to create an ERC721Contract instance.

    Args:
        web3_client: Web3 client instance
        contract_address: ERC721 contract address
        config: Configuration dictionary

    Returns:
        ERC721Contract instance
    """
    return ERC721Contract(
        web3_client=web3_client,
        contract_address=contract_address,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the ERC721 contract
    pass
