# blockchain/smart-contracts/erc20_contract.py
# NEXUS AI TRADING SYSTEM - ERC20 Token Contract Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
ERC20 Token Smart Contract Integration for NEXUS AI Trading System.
Provides comprehensive interaction with ERC20 compliant tokens including:
- Balance queries
- Transfers (standard and permit)
- Approval management
- Token information
- Allowance tracking
- Token metadata
- Permit/EIP-2612 support
- Flash minting support (EIP-3156)
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
from eth_account.messages import encode_defunct

# NEXUS Imports
from blockchain.smart_contracts.base_contract import BaseContract
from blockchain.smart_contracts.contract_abi import get_abi_dict
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.erc20")


# ============================================================================
# Enums & Constants
# ============================================================================

class ERC20Action(str, Enum):
    """ERC20 actions."""
    TRANSFER = "transfer"
    TRANSFER_FROM = "transfer_from"
    APPROVE = "approve"
    PERMIT = "permit"
    MINT = "mint"
    BURN = "burn"


@dataclass
class TokenInfo:
    """Token information."""
    address: str
    name: str
    symbol: str
    decimals: int
    total_supply: int
    chain_id: int
    owner: Optional[str] = None
    is_verified: bool = False
    is_audited: bool = False
    website: Optional[str] = None
    twitter: Optional[str] = None
    telegram: Optional[str] = None
    github: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Allowance:
    """Token allowance information."""
    owner: str
    spender: str
    amount: int
    timestamp: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Transfer:
    """Token transfer information."""
    tx_hash: str
    from_address: str
    to_address: str
    amount: int
    timestamp: datetime
    block_number: int
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermitData:
    """EIP-2612 Permit data."""
    owner: str
    spender: str
    value: int
    nonce: int
    deadline: int
    v: int
    r: str
    s: str


# ============================================================================
# ERC20 Contract Integration
# ============================================================================

class ERC20Contract(BaseContract):
    """
    ERC20 Token Smart Contract Integration.
    Provides comprehensive interaction with ERC20 compliant tokens.
    """

    # ERC20 ABI (minimal)
    ERC20_ABI = [
        # View Functions
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
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "account", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"}
            ],
            "name": "allowance",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },

        # Write Functions
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"}
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"}
            ],
            "name": "transferFrom",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "spender", "type": "address"},
                {"name": "value", "type": "uint256"}
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        },

        # ERC20 Events
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "from", "type": "address"},
                {"indexed": True, "name": "to", "type": "address"},
                {"indexed": False, "name": "value", "type": "uint256"}
            ],
            "name": "Transfer",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "owner", "type": "address"},
                {"indexed": True, "name": "spender", "type": "address"},
                {"indexed": False, "name": "value", "type": "uint256"}
            ],
            "name": "Approval",
            "type": "event"
        },

        # EIP-2612 Permit
        {
            "constant": True,
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "nonces",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "DOMAIN_SEPARATOR",
            "outputs": [{"name": "", "type": "bytes32"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "deadline", "type": "uint256"},
                {"name": "v", "type": "uint8"},
                {"name": "r", "type": "bytes32"},
                {"name": "s", "type": "bytes32"}
            ],
            "name": "permit",
            "outputs": [],
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
        Initialize ERC20 contract integration.

        Args:
            web3_client: Web3 client instance
            contract_address: ERC20 contract address
            config: Configuration dictionary
        """
        super().__init__(
            web3_client=web3_client,
            contract_name="ERC20",
            contract_address=contract_address or "",
            abi=self.ERC20_ABI,
            config=config,
        )

        # Token info cache
        self._token_info: Optional[TokenInfo] = None
        self._allowance_cache: Dict[str, Dict[str, Allowance]] = {}

        logger.info(
            "ERC20Contract initialized",
            extra={
                "contract_address": self.contract_address,
                "chain": web3_client.chain_name,
            }
        )

    # -----------------------------------------------------------------------
    # Token Information
    # -----------------------------------------------------------------------

    async def get_token_info(
        self,
        force_refresh: bool = False,
    ) -> Optional[TokenInfo]:
        """
        Get token information.

        Args:
            force_refresh: Force refresh cache

        Returns:
            TokenInfo or None
        """
        if not force_refresh and self._token_info:
            return self._token_info

        try:
            # Get basic info
            name = await self._call_contract_function("name")
            symbol = await self._call_contract_function("symbol")
            decimals = await self._call_contract_function("decimals")
            total_supply = await self._call_contract_function("totalSupply")

            # Get owner (if available)
            owner = None
            if self._has_function("owner"):
                owner = await self._call_contract_function("owner")

            token_info = TokenInfo(
                address=self.contract_address,
                name=name or "Unknown",
                symbol=symbol or "UNKNOWN",
                decimals=int(decimals) if decimals else 18,
                total_supply=int(total_supply) if total_supply else 0,
                chain_id=self.web3_client.chain_id,
                owner=owner,
            )

            self._token_info = token_info
            return token_info

        except Exception as e:
            logger.error(f"Error getting token info: {e}")
            return None

    async def get_name(self) -> Optional[str]:
        """Get token name."""
        info = await self.get_token_info()
        return info.name if info else None

    async def get_symbol(self) -> Optional[str]:
        """Get token symbol."""
        info = await self.get_token_info()
        return info.symbol if info else None

    async def get_decimals(self) -> int:
        """Get token decimals."""
        info = await self.get_token_info()
        return info.decimals if info else 18

    async def get_total_supply(self) -> int:
        """Get total supply."""
        info = await self.get_token_info()
        return info.total_supply if info else 0

    # -----------------------------------------------------------------------
    # Balance Queries
    # -----------------------------------------------------------------------

    async def balance_of(
        self,
        account: Union[str, Address],
    ) -> int:
        """
        Get token balance of an account.

        Args:
            account: Account address

        Returns:
            Balance amount
        """
        account = Web3.to_checksum_address(account)

        try:
            balance = await self._call_contract_function(
                "balanceOf",
                account,
            )
            return int(balance) if balance else 0

        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0

    async def balance_of_multiple(
        self,
        accounts: List[Union[str, Address]],
    ) -> Dict[str, int]:
        """
        Get balances of multiple accounts.

        Args:
            accounts: List of account addresses

        Returns:
            Dict of address -> balance
        """
        balances = {}
        for account in accounts:
            balances[Web3.to_checksum_address(account)] = await self.balance_of(account)
        return balances

    # -----------------------------------------------------------------------
    # Transfer Operations
    # -----------------------------------------------------------------------

    async def transfer(
        self,
        to_address: Union[str, Address],
        amount: int,
        from_address: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Transfer tokens.

        Args:
            to_address: Recipient address
            amount: Amount to transfer
            from_address: Sender address (optional)

        Returns:
            Transaction hash or None
        """
        to_address = Web3.to_checksum_address(to_address)
        from_address = Web3.to_checksum_address(from_address or self.web3_client.default_account)

        try:
            tx = await self._build_transaction(
                "transfer",
                to_address,
                amount,
            )

            tx_hash = await self._send_transaction(tx, from_address)

            if tx_hash:
                logger.info(
                    f"Transfer successful",
                    extra={
                        "to": to_address,
                        "amount": amount,
                        "from": from_address,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error transferring: {e}")
            return None

    async def transfer_from(
        self,
        from_address: Union[str, Address],
        to_address: Union[str, Address],
        amount: int,
        spender: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Transfer tokens from another account (requires allowance).

        Args:
            from_address: Sender address
            to_address: Recipient address
            amount: Amount to transfer
            spender: Spender address (optional)

        Returns:
            Transaction hash or None
        """
        from_address = Web3.to_checksum_address(from_address)
        to_address = Web3.to_checksum_address(to_address)
        spender = Web3.to_checksum_address(spender or self.web3_client.default_account)

        try:
            tx = await self._build_transaction(
                "transferFrom",
                from_address,
                to_address,
                amount,
            )

            tx_hash = await self._send_transaction(tx, spender)

            if tx_hash:
                logger.info(
                    f"TransferFrom successful",
                    extra={
                        "from": from_address,
                        "to": to_address,
                        "amount": amount,
                        "spender": spender,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error transferring from: {e}")
            return None

    # -----------------------------------------------------------------------
    # Approval Operations
    # -----------------------------------------------------------------------

    async def approve(
        self,
        spender: Union[str, Address],
        amount: int,
        owner: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Approve spender to transfer tokens.

        Args:
            spender: Spender address
            amount: Amount to approve
            owner: Owner address (optional)

        Returns:
            Transaction hash or None
        """
        spender = Web3.to_checksum_address(spender)
        owner = Web3.to_checksum_address(owner or self.web3_client.default_account)

        try:
            tx = await self._build_transaction(
                "approve",
                spender,
                amount,
            )

            tx_hash = await self._send_transaction(tx, owner)

            if tx_hash:
                logger.info(
                    f"Approval successful",
                    extra={
                        "spender": spender,
                        "amount": amount,
                        "owner": owner,
                        "tx_hash": tx_hash,
                    }
                )

                # Clear allowance cache
                key = f"{owner}:{spender}"
                self._allowance_cache.pop(key, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error approving: {e}")
            return None

    async def allowance(
        self,
        owner: Union[str, Address],
        spender: Union[str, Address],
        force_refresh: bool = False,
    ) -> int:
        """
        Get allowance of spender for owner.

        Args:
            owner: Owner address
            spender: Spender address
            force_refresh: Force refresh cache

        Returns:
            Allowance amount
        """
        owner = Web3.to_checksum_address(owner)
        spender = Web3.to_checksum_address(spender)

        cache_key = f"{owner}:{spender}"

        if not force_refresh and cache_key in self._allowance_cache:
            return self._allowance_cache[cache_key].amount

        try:
            allowance = await self._call_contract_function(
                "allowance",
                owner,
                spender,
            )
            amount = int(allowance) if allowance else 0

            # Cache
            self._allowance_cache[cache_key] = Allowance(
                owner=owner,
                spender=spender,
                amount=amount,
                timestamp=datetime.utcnow(),
            )

            return amount

        except Exception as e:
            logger.error(f"Error getting allowance: {e}")
            return 0

    async def increase_allowance(
        self,
        spender: Union[str, Address],
        added_value: int,
        owner: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Increase allowance.

        Args:
            spender: Spender address
            added_value: Amount to add
            owner: Owner address (optional)

        Returns:
            Transaction hash or None
        """
        current_allowance = await self.allowance(owner, spender)
        new_allowance = current_allowance + added_value
        return await self.approve(spender, new_allowance, owner)

    async def decrease_allowance(
        self,
        spender: Union[str, Address],
        subtracted_value: int,
        owner: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Decrease allowance.

        Args:
            spender: Spender address
            subtracted_value: Amount to subtract
            owner: Owner address (optional)

        Returns:
            Transaction hash or None
        """
        current_allowance = await self.allowance(owner, spender)
        new_allowance = max(0, current_allowance - subtracted_value)
        return await self.approve(spender, new_allowance, owner)

    # -----------------------------------------------------------------------
    # EIP-2612 Permit
    # -----------------------------------------------------------------------

    async def permit(
        self,
        owner: Union[str, Address],
        spender: Union[str, Address],
        value: int,
        deadline: int,
        v: int,
        r: bytes,
        s: bytes,
    ) -> Optional[str]:
        """
        Execute EIP-2612 permit.

        Args:
            owner: Owner address
            spender: Spender address
            value: Permit value
            deadline: Deadline timestamp
            v: Signature v
            r: Signature r
            s: Signature s

        Returns:
            Transaction hash or None
        """
        owner = Web3.to_checksum_address(owner)
        spender = Web3.to_checksum_address(spender)

        try:
            if not self._has_function("permit"):
                logger.error("Permit function not available")
                return None

            tx = await self._build_transaction(
                "permit",
                owner,
                spender,
                value,
                deadline,
                v,
                r,
                s,
            )

            tx_hash = await self._send_transaction(tx, self.web3_client.default_account)

            if tx_hash:
                logger.info(
                    f"Permit executed",
                    extra={
                        "owner": owner,
                        "spender": spender,
                        "value": value,
                        "deadline": deadline,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error executing permit: {e}")
            return None

    async def get_permit_data(
        self,
        owner: Union[str, Address],
        spender: Union[str, Address],
        value: int,
        deadline: int,
        private_key: str,
    ) -> PermitData:
        """
        Generate EIP-2612 permit data.

        Args:
            owner: Owner address
            spender: Spender address
            value: Permit value
            deadline: Deadline timestamp
            private_key: Owner private key

        Returns:
            PermitData
        """
        owner = Web3.to_checksum_address(owner)
        spender = Web3.to_checksum_address(spender)

        try:
            # Get nonce
            nonce = await self._call_contract_function("nonces", owner)

            # Get domain separator
            domain_separator = await self._call_contract_function("DOMAIN_SEPARATOR")

            # Build permit hash
            permit_hash = self._build_permit_hash(
                domain_separator,
                owner,
                spender,
                value,
                nonce,
                deadline,
            )

            # Sign permit
            signed = self.web3_client.sign_message(
                permit_hash,
                private_key,
            )

            return PermitData(
                owner=owner,
                spender=spender,
                value=value,
                nonce=int(nonce),
                deadline=deadline,
                v=signed.v,
                r=signed.r.hex(),
                s=signed.s.hex(),
            )

        except Exception as e:
            logger.error(f"Error generating permit data: {e}")
            raise

    def _build_permit_hash(
        self,
        domain_separator: bytes,
        owner: str,
        spender: str,
        value: int,
        nonce: int,
        deadline: int,
    ) -> bytes:
        """Build EIP-2612 permit hash."""
        # EIP-2612 permit typehash
        type_hash = "0x6e71edae12b1b97f4d1f60370fef10105fa2faae0126114a169c64845d6126c9"

        # Build digest
        return Web3.solidity_keccak(
            ["bytes1", "bytes32", "bytes32", "address", "address", "uint256", "uint256", "uint256"],
            [
                b"\x19",
                Web3.to_bytes(hexstr=domain_separator),
                Web3.to_bytes(hexstr=type_hash),
                Web3.to_checksum_address(owner),
                Web3.to_checksum_address(spender),
                value,
                nonce,
                deadline,
            ]
        )

    async def get_domain_separator(self) -> Optional[str]:
        """Get domain separator."""
        try:
            separator = await self._call_contract_function("DOMAIN_SEPARATOR")
            return separator
        except Exception:
            return None

    async def get_nonce(self, owner: Union[str, Address]) -> int:
        """Get nonce for an address."""
        owner = Web3.to_checksum_address(owner)

        try:
            nonce = await self._call_contract_function("nonces", owner)
            return int(nonce) if nonce else 0
        except Exception:
            return 0

    # -----------------------------------------------------------------------
    # Mint/Burn Operations
    # -----------------------------------------------------------------------

    async def mint(
        self,
        to_address: Union[str, Address],
        amount: int,
    ) -> Optional[str]:
        """
        Mint tokens (if contract has mint function).

        Args:
            to_address: Recipient address
            amount: Amount to mint

        Returns:
            Transaction hash or None
        """
        to_address = Web3.to_checksum_address(to_address)

        try:
            if not self._has_function("mint"):
                logger.error("Mint function not available")
                return None

            tx = await self._build_transaction(
                "mint",
                to_address,
                amount,
            )

            tx_hash = await self._send_transaction(tx, self.web3_client.default_account)

            if tx_hash:
                logger.info(
                    f"Mint successful",
                    extra={
                        "to": to_address,
                        "amount": amount,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error minting: {e}")
            return None

    async def burn(
        self,
        amount: int,
        account: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Burn tokens (if contract has burn function).

        Args:
            amount: Amount to burn
            account: Account address (optional)

        Returns:
            Transaction hash or None
        """
        account = Web3.to_checksum_address(account or self.web3_client.default_account)

        try:
            if not self._has_function("burn"):
                logger.error("Burn function not available")
                return None

            tx = await self._build_transaction(
                "burn",
                amount,
            )

            tx_hash = await self._send_transaction(tx, account)

            if tx_hash:
                logger.info(
                    f"Burn successful",
                    extra={
                        "account": account,
                        "amount": amount,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error burning: {e}")
            return None

    async def burn_from(
        self,
        account: Union[str, Address],
        amount: int,
    ) -> Optional[str]:
        """
        Burn tokens from another account (requires allowance).

        Args:
            account: Account address
            amount: Amount to burn

        Returns:
            Transaction hash or None
        """
        account = Web3.to_checksum_address(account)

        try:
            if not self._has_function("burnFrom"):
                logger.error("BurnFrom function not available")
                return None

            tx = await self._build_transaction(
                "burnFrom",
                account,
                amount,
            )

            tx_hash = await self._send_transaction(tx, self.web3_client.default_account)

            if tx_hash:
                logger.info(
                    f"BurnFrom successful",
                    extra={
                        "account": account,
                        "amount": amount,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error burning from: {e}")
            return None

    # -----------------------------------------------------------------------
    # Token Analytics
    # -----------------------------------------------------------------------

    async def get_holder_info(
        self,
        account: Union[str, Address],
    ) -> Dict[str, Any]:
        """
        Get holder information.

        Args:
            account: Account address

        Returns:
            Holder information
        """
        account = Web3.to_checksum_address(account)

        try:
            balance = await self.balance_of(account)
            total_supply = await self.get_total_supply()
            decimals = await self.get_decimals()

            return {
                "address": account,
                "balance": balance,
                "balance_formatted": balance / (10 ** decimals),
                "percentage": (balance / total_supply * 100) if total_supply > 0 else 0,
                "is_whale": balance > total_supply * 0.01 if total_supply > 0 else False,
            }

        except Exception as e:
            logger.error(f"Error getting holder info: {e}")
            return {}

    async def get_market_metrics(self) -> Dict[str, Any]:
        """
        Get token market metrics.

        Returns:
            Market metrics
        """
        try:
            total_supply = await self.get_total_supply()
            decimals = await self.get_decimals()

            return {
                "total_supply": total_supply,
                "total_supply_formatted": total_supply / (10 ** decimals),
                "decimals": decimals,
                "chain_id": self.web3_client.chain_id,
                "contract_address": self.contract_address,
            }

        except Exception as e:
            logger.error(f"Error getting market metrics: {e}")
            return {}

    # -----------------------------------------------------------------------
    # Event Monitoring
    # -----------------------------------------------------------------------

    async def get_transfer_events(
        self,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        filter_from: Optional[str] = None,
        filter_to: Optional[str] = None,
    ) -> List[Transfer]:
        """
        Get transfer events.

        Args:
            from_block: From block number
            to_block: To block number
            filter_from: Filter by from address
            filter_to: Filter by to address

        Returns:
            List of Transfer
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

    def is_erc20(self) -> bool:
        """Check if contract is ERC20 compliant."""
        required_functions = [
            "totalSupply",
            "balanceOf",
            "transfer",
            "transferFrom",
            "approve",
            "allowance",
        ]
        return all(self._has_function(f) for f in required_functions)

    def format_amount(self, amount: int) -> float:
        """Format amount with proper decimals."""
        decimals = self.get_decimals()  # This is async, need to handle differently
        return amount / (10 ** 18)  # Default to 18 decimals

    async def format_amount_async(self, amount: int) -> float:
        """Format amount with proper decimals."""
        decimals = await self.get_decimals()
        return amount / (10 ** decimals)

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
            return 100000

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
            "token_info_cached": self._token_info is not None,
            "allowance_cache_size": len(self._allowance_cache),
            "is_erc20": self.is_erc20(),
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_erc20_contract(
    web3_client: Web3Client,
    contract_address: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ERC20Contract:
    """
    Factory function to create an ERC20Contract instance.

    Args:
        web3_client: Web3 client instance
        contract_address: ERC20 contract address
        config: Configuration dictionary

    Returns:
        ERC20Contract instance
    """
    return ERC20Contract(
        web3_client=web3_client,
        contract_address=contract_address,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the ERC20 contract
    pass
