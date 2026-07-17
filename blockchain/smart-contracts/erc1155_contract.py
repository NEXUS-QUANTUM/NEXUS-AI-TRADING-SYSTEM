# blockchain/smart-contracts/erc1155_contract.py
# NEXUS AI TRADING SYSTEM - ERC1155 Multi-Token Contract Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
ERC1155 Multi-Token Smart Contract Integration for NEXUS AI Trading System.
Provides comprehensive interaction with ERC1155 compliant contracts including:
- Token management (mint, burn, transfer)
- Batch operations
- URI management
- Balance tracking
- Approval handling
- Metadata management
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

logger = get_logger("nexus.blockchain.erc1155")


# ============================================================================
# Enums & Constants
# ============================================================================

class ERC1155Action(str, Enum):
    """ERC1155 actions."""
    MINT = "mint"
    BURN = "burn"
    TRANSFER = "transfer"
    TRANSFER_BATCH = "transfer_batch"
    APPROVE = "approve"
    SET_URI = "set_uri"
    SET_APPROVAL = "set_approval"


@dataclass
class TokenInfo:
    """ERC1155 token information."""
    token_id: int
    uri: str
    supply: int
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenBalance:
    """Token balance information."""
    token_id: int
    account: str
    balance: int
    last_updated: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransferData:
    """Token transfer data."""
    token_id: int
    from_address: str
    to_address: str
    amount: int
    timestamp: datetime
    transaction_hash: str
    block_number: int
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# ERC1155 Contract Integration
# ============================================================================

class ERC1155Contract(BaseContract):
    """
    ERC1155 Multi-Token Smart Contract Integration.
    Provides comprehensive interaction with ERC1155 compliant contracts.
    """

    # ERC1155 ABI (minimal)
    ERC1155_ABI = [
        # View Functions
        {
            "constant": True,
            "inputs": [
                {"name": "account", "type": "address"},
                {"name": "id", "type": "uint256"}
            ],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {"name": "accounts", "type": "address[]"},
                {"name": "ids", "type": "uint256[]"}
            ],
            "name": "balanceOfBatch",
            "outputs": [{"name": "", "type": "uint256[]"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {"name": "account", "type": "address"},
                {"name": "operator", "type": "address"}
            ],
            "name": "isApprovedForAll",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "id", "type": "uint256"}],
            "name": "uri",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "supportsInterface",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        },

        # Write Functions
        {
            "constant": False,
            "inputs": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "id", "type": "uint256"},
                {"name": "amount", "type": "uint256"},
                {"name": "data", "type": "bytes"}
            ],
            "name": "safeTransferFrom",
            "outputs": [],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "ids", "type": "uint256[]"},
                {"name": "amounts", "type": "uint256[]"},
                {"name": "data", "type": "bytes"}
            ],
            "name": "safeBatchTransferFrom",
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
        {
            "constant": False,
            "inputs": [
                {"name": "id", "type": "uint256"},
                {"name": "uri", "type": "string"}
            ],
            "name": "setURI",
            "outputs": [],
            "type": "function"
        },

        # Mint Functions (often custom)
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "id", "type": "uint256"},
                {"name": "amount", "type": "uint256"},
                {"name": "data", "type": "bytes"}
            ],
            "name": "mint",
            "outputs": [],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "ids", "type": "uint256[]"},
                {"name": "amounts", "type": "uint256[]"},
                {"name": "data", "type": "bytes"}
            ],
            "name": "mintBatch",
            "outputs": [],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "account", "type": "address"},
                {"name": "id", "type": "uint256"},
                {"name": "amount", "type": "uint256"}
            ],
            "name": "burn",
            "outputs": [],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "account", "type": "address"},
                {"name": "ids", "type": "uint256[]"},
                {"name": "amounts", "type": "uint256[]"}
            ],
            "name": "burnBatch",
            "outputs": [],
            "type": "function"
        },

        # Events
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "operator", "type": "address"},
                {"indexed": True, "name": "from", "type": "address"},
                {"indexed": True, "name": "to", "type": "address"},
                {"indexed": False, "name": "id", "type": "uint256"},
                {"indexed": False, "name": "value", "type": "uint256"}
            ],
            "name": "TransferSingle",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "operator", "type": "address"},
                {"indexed": True, "name": "from", "type": "address"},
                {"indexed": True, "name": "to", "type": "address"},
                {"indexed": False, "name": "ids", "type": "uint256[]"},
                {"indexed": False, "name": "values", "type": "uint256[]"}
            ],
            "name": "TransferBatch",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "account", "type": "address"},
                {"indexed": True, "name": "operator", "type": "address"},
                {"indexed": False, "name": "approved", "type": "bool"}
            ],
            "name": "ApprovalForAll",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": False, "name": "value", "type": "string"},
                {"indexed": True, "name": "id", "type": "uint256"}
            ],
            "name": "URI",
            "type": "event"
        }
    ]

    def __init__(
        self,
        web3_client: Web3Client,
        contract_address: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ERC1155 contract integration.

        Args:
            web3_client: Web3 client instance
            contract_address: ERC1155 contract address
            config: Configuration dictionary
        """
        super().__init__(
            web3_client=web3_client,
            contract_name="ERC1155",
            contract_address=contract_address or "",
            abi=self.ERC1155_ABI,
            config=config,
        )

        # Token cache
        self._token_cache: Dict[int, TokenInfo] = {}
        self._balance_cache: Dict[str, Dict[int, TokenBalance]] = {}

        # Token statistics
        self._token_stats: Dict[int, Dict[str, Any]] = {}

        # Metadata resolver
        self._metadata_resolver = self._create_metadata_resolver()

        logger.info(
            "ERC1155Contract initialized",
            extra={
                "contract_address": self.contract_address,
                "chain": web3_client.chain_name,
            }
        )

    # -----------------------------------------------------------------------
    # Balance Queries
    # -----------------------------------------------------------------------

    async def balance_of(
        self,
        account: Union[str, Address],
        token_id: int,
    ) -> int:
        """
        Get balance of a specific token for an account.

        Args:
            account: Account address
            token_id: Token ID

        Returns:
            Balance amount
        """
        account = Web3.to_checksum_address(account)

        try:
            balance = await self._call_contract_function(
                "balanceOf",
                account,
                token_id,
            )
            return int(balance) if balance else 0

        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0

    async def balance_of_batch(
        self,
        accounts: List[Union[str, Address]],
        token_ids: List[int],
    ) -> List[int]:
        """
        Get balances for multiple accounts and tokens.

        Args:
            accounts: List of account addresses
            token_ids: List of token IDs

        Returns:
            List of balances
        """
        accounts = [Web3.to_checksum_address(a) for a in accounts]

        try:
            balances = await self._call_contract_function(
                "balanceOfBatch",
                accounts,
                token_ids,
            )
            return [int(b) for b in balances] if balances else []

        except Exception as e:
            logger.error(f"Error getting batch balances: {e}")
            return []

    async def get_all_balances(
        self,
        account: Union[str, Address],
        token_ids: Optional[List[int]] = None,
    ) -> Dict[int, int]:
        """
        Get balances for all tokens of an account.

        Args:
            account: Account address
            token_ids: Specific token IDs (optional)

        Returns:
            Dict of token_id -> balance
        """
        account = Web3.to_checksum_address(account)

        if token_ids is None:
            token_ids = await self.get_all_token_ids()

        if not token_ids:
            return {}

        balances = {}
        for token_id in token_ids:
            balance = await self.balance_of(account, token_id)
            if balance > 0:
                balances[token_id] = balance

        return balances

    # -----------------------------------------------------------------------
    # Token Information
    # -----------------------------------------------------------------------

    async def get_token_info(
        self,
        token_id: int,
        force_refresh: bool = False,
    ) -> Optional[TokenInfo]:
        """
        Get token information.

        Args:
            token_id: Token ID
            force_refresh: Force refresh cache

        Returns:
            TokenInfo or None
        """
        if not force_refresh and token_id in self._token_cache:
            return self._token_cache[token_id]

        try:
            # Get URI
            uri = await self._call_contract_function("uri", token_id)

            # Get supply (if available)
            supply = await self._get_token_supply(token_id)

            # Get metadata
            metadata = await self._fetch_metadata(uri) if uri else None

            token_info = TokenInfo(
                token_id=token_id,
                uri=uri or "",
                supply=supply or 0,
                metadata=metadata,
                created_at=datetime.utcnow(),
                attributes=metadata.get("attributes", {}) if metadata else {},
            )

            self._token_cache[token_id] = token_info
            return token_info

        except Exception as e:
            logger.error(f"Error getting token info for {token_id}: {e}")
            return None

    async def get_token_metadata(
        self,
        token_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get token metadata.

        Args:
            token_id: Token ID

        Returns:
            Metadata dict or None
        """
        token_info = await self.get_token_info(token_id)
        return token_info.metadata if token_info else None

    async def get_token_uri(self, token_id: int) -> Optional[str]:
        """
        Get token URI.

        Args:
            token_id: Token ID

        Returns:
            URI string or None
        """
        try:
            uri = await self._call_contract_function("uri", token_id)
            return uri
        except Exception:
            return None

    async def get_all_token_ids(self) -> List[int]:
        """
        Get all token IDs.

        Returns:
            List of token IDs
        """
        # In production, would use an indexer or events
        # For now, return cached IDs
        return list(self._token_cache.keys())

    async def get_token_supply(self, token_id: int) -> int:
        """
        Get total supply of a token.

        Args:
            token_id: Token ID

        Returns:
            Total supply
        """
        try:
            supply = await self._call_contract_function("totalSupply", token_id)
            return int(supply) if supply else 0
        except Exception:
            # Not all ERC1155 contracts have totalSupply
            return 0

    async def _get_token_supply(self, token_id: int) -> Optional[int]:
        """Get token supply (internal)."""
        return await self.get_token_supply(token_id)

    # -----------------------------------------------------------------------
    # Transfer Operations
    # -----------------------------------------------------------------------

    async def safe_transfer_from(
        self,
        from_address: Union[str, Address],
        to_address: Union[str, Address],
        token_id: int,
        amount: int,
        data: Optional[bytes] = None,
    ) -> Optional[str]:
        """
        Transfer a token.

        Args:
            from_address: From address
            to_address: To address
            token_id: Token ID
            amount: Amount to transfer
            data: Additional data

        Returns:
            Transaction hash or None
        """
        from_address = Web3.to_checksum_address(from_address)
        to_address = Web3.to_checksum_address(to_address)

        try:
            tx = await self._build_transaction(
                "safeTransferFrom",
                from_address,
                to_address,
                token_id,
                amount,
                data or b"",
            )

            tx_hash = await self._send_transaction(tx, from_address)

            if tx_hash:
                logger.info(
                    f"Transfer successful",
                    extra={
                        "from": from_address,
                        "to": to_address,
                        "token_id": token_id,
                        "amount": amount,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error transferring: {e}")
            return None

    async def safe_batch_transfer_from(
        self,
        from_address: Union[str, Address],
        to_address: Union[str, Address],
        token_ids: List[int],
        amounts: List[int],
        data: Optional[bytes] = None,
    ) -> Optional[str]:
        """
        Batch transfer multiple tokens.

        Args:
            from_address: From address
            to_address: To address
            token_ids: List of token IDs
            amounts: List of amounts
            data: Additional data

        Returns:
            Transaction hash or None
        """
        from_address = Web3.to_checksum_address(from_address)
        to_address = Web3.to_checksum_address(to_address)

        if len(token_ids) != len(amounts):
            logger.error("Token IDs and amounts must have same length")
            return None

        try:
            tx = await self._build_transaction(
                "safeBatchTransferFrom",
                from_address,
                to_address,
                token_ids,
                amounts,
                data or b"",
            )

            tx_hash = await self._send_transaction(tx, from_address)

            if tx_hash:
                logger.info(
                    f"Batch transfer successful",
                    extra={
                        "from": from_address,
                        "to": to_address,
                        "token_ids": token_ids,
                        "amounts": amounts,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error batch transferring: {e}")
            return None

    # -----------------------------------------------------------------------
    # Approval Operations
    # -----------------------------------------------------------------------

    async def set_approval_for_all(
        self,
        operator: Union[str, Address],
        approved: bool,
        from_address: Union[str, Address],
    ) -> Optional[str]:
        """
        Set approval for all tokens.

        Args:
            operator: Operator address
            approved: Approval status
            from_address: From address

        Returns:
            Transaction hash or None
        """
        operator = Web3.to_checksum_address(operator)
        from_address = Web3.to_checksum_address(from_address)

        try:
            tx = await self._build_transaction(
                "setApprovalForAll",
                operator,
                approved,
            )

            tx_hash = await self._send_transaction(tx, from_address)

            if tx_hash:
                logger.info(
                    f"Approval set",
                    extra={
                        "operator": operator,
                        "approved": approved,
                        "from": from_address,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error setting approval: {e}")
            return None

    async def is_approved_for_all(
        self,
        account: Union[str, Address],
        operator: Union[str, Address],
    ) -> bool:
        """
        Check if operator is approved for all tokens.

        Args:
            account: Account address
            operator: Operator address

        Returns:
            Approval status
        """
        account = Web3.to_checksum_address(account)
        operator = Web3.to_checksum_address(operator)

        try:
            approved = await self._call_contract_function(
                "isApprovedForAll",
                account,
                operator,
            )
            return bool(approved) if approved is not None else False

        except Exception as e:
            logger.error(f"Error checking approval: {e}")
            return False

    # -----------------------------------------------------------------------
    # Mint Operations
    # -----------------------------------------------------------------------

    async def mint(
        self,
        to_address: Union[str, Address],
        token_id: int,
        amount: int,
        data: Optional[bytes] = None,
    ) -> Optional[str]:
        """
        Mint a token.

        Args:
            to_address: Recipient address
            token_id: Token ID
            amount: Amount to mint
            data: Additional data

        Returns:
            Transaction hash or None
        """
        to_address = Web3.to_checksum_address(to_address)

        try:
            # Check if mint function exists
            if not self._has_function("mint"):
                logger.error("Mint function not available")
                return None

            tx = await self._build_transaction(
                "mint",
                to_address,
                token_id,
                amount,
                data or b"",
            )

            tx_hash = await self._send_transaction(tx, self.web3_client.default_account)

            if tx_hash:
                logger.info(
                    f"Mint successful",
                    extra={
                        "to": to_address,
                        "token_id": token_id,
                        "amount": amount,
                        "tx_hash": tx_hash,
                    }
                )

                # Clear cache
                self._token_cache.pop(token_id, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error minting: {e}")
            return None

    async def mint_batch(
        self,
        to_address: Union[str, Address],
        token_ids: List[int],
        amounts: List[int],
        data: Optional[bytes] = None,
    ) -> Optional[str]:
        """
        Batch mint multiple tokens.

        Args:
            to_address: Recipient address
            token_ids: List of token IDs
            amounts: List of amounts
            data: Additional data

        Returns:
            Transaction hash or None
        """
        to_address = Web3.to_checksum_address(to_address)

        if len(token_ids) != len(amounts):
            logger.error("Token IDs and amounts must have same length")
            return None

        try:
            if not self._has_function("mintBatch"):
                logger.error("MintBatch function not available")
                return None

            tx = await self._build_transaction(
                "mintBatch",
                to_address,
                token_ids,
                amounts,
                data or b"",
            )

            tx_hash = await self._send_transaction(tx, self.web3_client.default_account)

            if tx_hash:
                logger.info(
                    f"Batch mint successful",
                    extra={
                        "to": to_address,
                        "token_ids": token_ids,
                        "amounts": amounts,
                        "tx_hash": tx_hash,
                    }
                )

                # Clear cache
                for token_id in token_ids:
                    self._token_cache.pop(token_id, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error batch minting: {e}")
            return None

    # -----------------------------------------------------------------------
    # Burn Operations
    # -----------------------------------------------------------------------

    async def burn(
        self,
        account: Union[str, Address],
        token_id: int,
        amount: int,
    ) -> Optional[str]:
        """
        Burn a token.

        Args:
            account: Account address
            token_id: Token ID
            amount: Amount to burn

        Returns:
            Transaction hash or None
        """
        account = Web3.to_checksum_address(account)

        try:
            if not self._has_function("burn"):
                logger.error("Burn function not available")
                return None

            tx = await self._build_transaction(
                "burn",
                account,
                token_id,
                amount,
            )

            tx_hash = await self._send_transaction(tx, account)

            if tx_hash:
                logger.info(
                    f"Burn successful",
                    extra={
                        "account": account,
                        "token_id": token_id,
                        "amount": amount,
                        "tx_hash": tx_hash,
                    }
                )

                # Clear cache
                self._token_cache.pop(token_id, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error burning: {e}")
            return None

    async def burn_batch(
        self,
        account: Union[str, Address],
        token_ids: List[int],
        amounts: List[int],
    ) -> Optional[str]:
        """
        Batch burn multiple tokens.

        Args:
            account: Account address
            token_ids: List of token IDs
            amounts: List of amounts

        Returns:
            Transaction hash or None
        """
        account = Web3.to_checksum_address(account)

        if len(token_ids) != len(amounts):
            logger.error("Token IDs and amounts must have same length")
            return None

        try:
            if not self._has_function("burnBatch"):
                logger.error("BurnBatch function not available")
                return None

            tx = await self._build_transaction(
                "burnBatch",
                account,
                token_ids,
                amounts,
            )

            tx_hash = await self._send_transaction(tx, account)

            if tx_hash:
                logger.info(
                    f"Batch burn successful",
                    extra={
                        "account": account,
                        "token_ids": token_ids,
                        "amounts": amounts,
                        "tx_hash": tx_hash,
                    }
                )

                # Clear cache
                for token_id in token_ids:
                    self._token_cache.pop(token_id, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error batch burning: {e}")
            return None

    # -----------------------------------------------------------------------
    # URI Management
    # -----------------------------------------------------------------------

    async def set_uri(
        self,
        token_id: int,
        new_uri: str,
    ) -> Optional[str]:
        """
        Set token URI.

        Args:
            token_id: Token ID
            new_uri: New URI

        Returns:
            Transaction hash or None
        """
        try:
            if not self._has_function("setURI"):
                logger.error("setURI function not available")
                return None

            tx = await self._build_transaction(
                "setURI",
                token_id,
                new_uri,
            )

            tx_hash = await self._send_transaction(tx, self.web3_client.default_account)

            if tx_hash:
                logger.info(
                    f"URI set",
                    extra={
                        "token_id": token_id,
                        "uri": new_uri,
                        "tx_hash": tx_hash,
                    }
                )

                # Clear cache
                self._token_cache.pop(token_id, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error setting URI: {e}")
            return None

    # -----------------------------------------------------------------------
    # Metadata Management
    # -----------------------------------------------------------------------

    async def _fetch_metadata(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata from URI.

        Args:
            uri: Metadata URI

        Returns:
            Metadata dict or None
        """
        try:
            if uri.startswith("ipfs://"):
                # Would use IPFS gateway
                return None
            elif uri.startswith("http"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(uri, timeout=10) as response:
                        if response.status == 200:
                            return await response.json()
            return None

        except Exception as e:
            logger.error(f"Error fetching metadata: {e}")
            return None

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
    # Token Statistics
    # -----------------------------------------------------------------------

    async def get_token_statistics(
        self,
        token_id: int,
    ) -> Dict[str, Any]:
        """
        Get token statistics.

        Args:
            token_id: Token ID

        Returns:
            Token statistics
        """
        if token_id in self._token_stats:
            return self._token_stats[token_id]

        stats = {
            "token_id": token_id,
            "total_supply": await self.get_token_supply(token_id),
            "holders": 0,
            "transfers": 0,
            "last_transfer": None,
            "metadata": await self.get_token_metadata(token_id),
        }

        # Would calculate from events in production

        self._token_stats[token_id] = stats
        return stats

    # -----------------------------------------------------------------------
    # Event Monitoring
    # -----------------------------------------------------------------------

    async def get_transfer_events(
        self,
        token_id: Optional[int] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ) -> List[TransferData]:
        """
        Get transfer events.

        Args:
            token_id: Filter by token ID
            from_block: From block number
            to_block: To block number

        Returns:
            List of TransferData
        """
        transfers = []

        try:
            # Would query events from blockchain
            # This is a placeholder implementation
            return transfers

        except Exception as e:
            logger.error(f"Error getting transfer events: {e}")
            return transfers

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def _has_function(self, function_name: str) -> bool:
        """Check if contract has a function."""
        for item in self.abi:
            if item.get("type") == "function" and item.get("name") == function_name:
                return True
        return False

    def supports_interface(self, interface_id: bytes) -> bool:
        """
        Check if contract supports an interface.

        Args:
            interface_id: Interface ID

        Returns:
            True if supported
        """
        try:
            result = self._call_contract_function("supportsInterface", interface_id)
            return bool(result)
        except Exception:
            return False

    def is_erc1155(self) -> bool:
        """Check if contract is ERC1155 compliant."""
        return self.supports_interface(b"\xd9\xb6\x7a\x26")

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
            return 200000

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
            "token_cache_size": len(self._token_cache),
            "balance_cache_size": len(self._balance_cache),
            "token_stats_size": len(self._token_stats),
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_erc1155_contract(
    web3_client: Web3Client,
    contract_address: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ERC1155Contract:
    """
    Factory function to create an ERC1155Contract instance.

    Args:
        web3_client: Web3 client instance
        contract_address: ERC1155 contract address
        config: Configuration dictionary

    Returns:
        ERC1155Contract instance
    """
    return ERC1155Contract(
        web3_client=web3_client,
        contract_address=contract_address,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the ERC1155 contract
    pass
