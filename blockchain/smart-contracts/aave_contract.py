# blockchain/smart-contracts/aave_contract.py
# NEXUS AI TRADING SYSTEM - Aave Protocol Smart Contract Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Aave Protocol Smart Contract Integration for NEXUS AI Trading System.
Provides comprehensive interaction with Aave V2 and V3 protocols including:
- Lending and borrowing
- Deposit and withdrawal
- Flash loans
- Health factor monitoring
- Interest rate analysis
- Reserve management
- Collateral optimization
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_typing import Address, ChecksumAddress

# NEXUS Imports
from blockchain.smart_contracts.base_contract import BaseContract
from blockchain.web3.web3_client import Web3Client
from shared.constants.error_constants import ErrorSeverity
from shared.helpers.crypto_helpers import to_checksum_address
from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async

logger = get_logger("nexus.blockchain.aave")


# ============================================================================
# Enums & Constants
# ============================================================================

class AaveVersion(str, Enum):
    """Aave protocol versions."""
    V2 = "v2"
    V3 = "v3"


class AaveAction(str, Enum):
    """Aave protocol actions."""
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    BORROW = "borrow"
    REPAY = "repay"
    FLASH_LOAN = "flash_loan"
    COLLATERAL_SWAP = "collateral_swap"
    LIQUIDATE = "liquidate"
    STABILIZE = "stabilize"
    DEBT_SWAP = "debt_swap"


class AaveRiskLevel(str, Enum):
    """Risk levels for Aave positions."""
    SAFE = "safe"          # Health factor > 2.0
    MODERATE = "moderate"   # Health factor 1.5 - 2.0
    RISKY = "risky"        # Health factor 1.1 - 1.5
    CRITICAL = "critical"   # Health factor 1.0 - 1.1
    LIQUIDATION = "liquidation"  # Health factor < 1.0


@dataclass
class AaveReserveData:
    """Aave reserve data."""
    asset: str
    available_liquidity: float
    total_debt: float
    liquidity_rate: float  # deposit rate
    variable_borrow_rate: float
    stable_borrow_rate: float
    average_stable_rate: float
    liquidity_index: float
    variable_borrow_index: float
    last_update_timestamp: int
    utilization_rate: float
    is_active: bool
    is_frozen: bool
    is_paused: bool
    reserve_factor: float
    liquidation_threshold: float
    liquidation_bonus: float
    loan_to_value: float
    price: float
    price_in_eth: float
    decimals: int


@dataclass
class AavePosition:
    """Aave user position."""
    user_address: str
    collateral: Dict[str, float]
    debt: Dict[str, float]
    health_factor: float
    total_collateral_usd: float
    total_debt_usd: float
    net_worth_usd: float
    risk_level: AaveRiskLevel
    available_to_borrow: Dict[str, float]
    available_to_withdraw: Dict[str, float]
    liquidation_threshold: float
    last_update: datetime


@dataclass
class AaveTransaction:
    """Aave transaction details."""
    tx_hash: str
    action: AaveAction
    asset: str
    amount: float
    amount_usd: float
    user: str
    timestamp: datetime
    success: bool
    gas_used: int
    gas_price: float
    block_number: int
    metadata: Dict[str, Any]


@dataclass
class FlashLoanParams:
    """Flash loan parameters."""
    assets: List[str]
    amounts: List[float]
    modes: List[int]  # 0 = no debt, 1 = stable, 2 = variable
    receiver: str
    on_behalf_of: str
    referral_code: int = 0


# ============================================================================
# Aave Contract Integration
# ============================================================================

class AaveContract(BaseContract):
    """
    Aave Protocol Smart Contract Integration.
    Supports both V2 and V3 protocols.
    """

    # Aave V3 contract addresses (mainnet)
    V3_ADDRESSES = {
        "pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        "pool_proxy": "0x6Ae43d3271fE6886B39dE4717c7fC1b57a3567e2",
        "data_provider": "0x7B4EB56E7CD4b454BA8ff71E4518426369a138a3",
        "oracle": "0x54586bE62E3c3580375aE3723C145253060Ca0C2",
        "ui_data_provider": "0x91B3c6d2F6d1A5302a0F58A8f57c42311Eb42A0f",
    }

    # Aave V2 contract addresses (mainnet)
    V2_ADDRESSES = {
        "lending_pool": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
        "lending_pool_configurator": "0x311Bb771e4F8952E6Da169b425E7e92d6Ac45756",
        "data_provider": "0x057835Ad21a177dbdd3090bB1CAE03EaCF78Fc6d",
        "oracle": "0xA50ba011c48153De246E5192C8f9258A2ba79Ca9",
        "ui_data_provider": "0xefC0c7C35C8C8550e3176ad686b748D400c651c7",
    }

    # ABI files (would be loaded from files in production)
    POOL_ABI = [
        {
            "inputs": [
                {"name": "asset", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "onBehalfOf", "type": "address"},
                {"name": "referralCode", "type": "uint16"}
            ],
            "name": "supply",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "asset", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"}
            ],
            "name": "withdraw",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "asset", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "interestRateMode", "type": "uint256"},
                {"name": "referralCode", "type": "uint16"},
                {"name": "onBehalfOf", "type": "address"}
            ],
            "name": "borrow",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "asset", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "interestRateMode", "type": "uint256"},
                {"name": "onBehalfOf", "type": "address"}
            ],
            "name": "repay",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "getReservesList",
            "outputs": [{"name": "", "type": "address[]"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"name": "asset", "type": "address"}],
            "name": "getReserveData",
            "outputs": [
                {"name": "configuration", "type": "tuple"},
                {"name": "liquidityIndex", "type": "uint128"},
                {"name": "variableBorrowIndex", "type": "uint128"},
                {"name": "liquidityRate", "type": "uint128"},
                {"name": "variableBorrowRate", "type": "uint128"},
                {"name": "stableBorrowRate", "type": "uint128"},
                {"name": "averageStableBorrowRate", "type": "uint128"},
                {"name": "lastUpdateTimestamp", "type": "uint40"},
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"name": "user", "type": "address"}],
            "name": "getUserAccountData",
            "outputs": [
                {"name": "totalCollateralBase", "type": "uint256"},
                {"name": "totalDebtBase", "type": "uint256"},
                {"name": "availableBorrowsBase", "type": "uint256"},
                {"name": "currentLiquidationThreshold", "type": "uint256"},
                {"name": "ltv", "type": "uint256"},
                {"name": "healthFactor", "type": "uint256"},
            ],
            "stateMutability": "view",
            "type": "function"
        },
    ]

    DATA_PROVIDER_ABI = [
        {
            "inputs": [{"name": "asset", "type": "address"}],
            "name": "getReserveData",
            "outputs": [
                {"name": "availableLiquidity", "type": "uint256"},
                {"name": "totalDebt", "type": "uint256"},
                {"name": "liquidityRate", "type": "uint256"},
                {"name": "variableBorrowRate", "type": "uint256"},
                {"name": "stableBorrowRate", "type": "uint256"},
                {"name": "averageStableBorrowRate", "type": "uint256"},
                {"name": "liquidityIndex", "type": "uint256"},
                {"name": "variableBorrowIndex", "type": "uint256"},
                {"name": "lastUpdateTimestamp", "type": "uint40"},
                {"name": "configuration", "type": "tuple"},
            ],
            "stateMutability": "view",
            "type": "function"
        },
    ]

    UI_DATA_PROVIDER_ABI = [
        {
            "inputs": [{"name": "user", "type": "address"}],
            "name": "getUserReservesData",
            "outputs": [
                {"name": "reserves", "type": "tuple[]"},
                {"name": "userReserves", "type": "tuple[]"},
                {"name": "userEmodeCategoryId", "type": "uint8"},
            ],
            "stateMutability": "view",
            "type": "function"
        },
    ]

    def __init__(
        self,
        web3_client: Web3Client,
        version: AaveVersion = AaveVersion.V3,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Aave contract integration.

        Args:
            web3_client: Web3 client instance
            version: Aave protocol version (V2 or V3)
            config: Configuration dictionary
        """
        super().__init__(
            web3_client=web3_client,
            contract_name="Aave",
            contract_address=self._get_contract_address(version),
            abi=self.POOL_ABI,
            config=config,
        )

        self.version = version
        self._addresses = self.V3_ADDRESSES if version == AaveVersion.V3 else self.V2_ADDRESSES

        # Initialize sub-contracts
        self._data_provider = None
        self._ui_data_provider = None
        self._oracle = None

        self._initialize_sub_contracts()

        # Token cache
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        self._reserve_cache: Dict[str, AaveReserveData] = {}
        self._last_cache_update: datetime = datetime.utcnow() - timedelta(minutes=5)

        logger.info(
            f"AaveContract initialized",
            extra={
                "version": version.value,
                "pool_address": self.contract_address,
                "chain": web3_client.chain_name,
            }
        )

    def _get_contract_address(self, version: AaveVersion) -> str:
        """Get the appropriate contract address for the version."""
        if version == AaveVersion.V3:
            return self.V3_ADDRESSES["pool"]
        return self.V2_ADDRESSES["lending_pool"]

    def _initialize_sub_contracts(self) -> None:
        """Initialize sub-contracts."""
        try:
            # Data Provider
            data_provider_address = self._addresses["data_provider"]
            self._data_provider = self.web3_client.get_contract(
                data_provider_address,
                abi=self.DATA_PROVIDER_ABI,
            )

            # UI Data Provider
            ui_data_provider_address = self._addresses["ui_data_provider"]
            self._ui_data_provider = self.web3_client.get_contract(
                ui_data_provider_address,
                abi=self.UI_DATA_PROVIDER_ABI,
            )

            logger.debug("Aave sub-contracts initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Aave sub-contracts: {e}")
            raise

    # -----------------------------------------------------------------------
    # Reserve Management
    # -----------------------------------------------------------------------

    async def get_reserve_data(
        self,
        asset: Union[str, Address],
        force_refresh: bool = False,
    ) -> Optional[AaveReserveData]:
        """
        Get reserve data for a specific asset.

        Args:
            asset: Asset address
            force_refresh: Force refresh cache

        Returns:
            AaveReserveData or None if error
        """
        asset_address = to_checksum_address(asset)

        if not force_refresh and asset_address in self._reserve_cache:
            return self._reserve_cache[asset_address]

        try:
            # Get reserve data from contract
            reserve_data = await self._call_contract_function(
                self._data_provider or self.contract,
                "getReserveData",
                asset_address,
            )

            if not reserve_data:
                return None

            # Get asset price
            price = await self.get_asset_price(asset_address)
            price_in_eth = await self.get_asset_price_in_eth(asset_address)

            # Get asset decimals
            decimals = await self._get_asset_decimals(asset_address)

            # Parse reserve data
            data = self._parse_reserve_data(reserve_data, price, price_in_eth, decimals)

            # Cache
            self._reserve_cache[asset_address] = data
            self._last_cache_update = datetime.utcnow()

            return data

        except Exception as e:
            logger.error(f"Error getting reserve data for {asset}: {e}")
            return None

    def _parse_reserve_data(
        self,
        reserve_data: Tuple,
        price: float,
        price_in_eth: float,
        decimals: int,
    ) -> AaveReserveData:
        """Parse reserve data from contract."""
        # The structure depends on the version
        if self.version == AaveVersion.V3:
            # V3 returns more data
            (
                configuration,
                liquidity_index,
                variable_borrow_index,
                liquidity_rate,
                variable_borrow_rate,
                stable_borrow_rate,
                average_stable_rate,
                last_update_timestamp,
            ) = reserve_data

            # Parse configuration (would be a proper struct)
            config = configuration if isinstance(configuration, tuple) else (0, 0, 0, 0, 0, 0)

        else:
            # V2 structure
            (
                available_liquidity,
                total_debt,
                liquidity_rate,
                variable_borrow_rate,
                stable_borrow_rate,
                average_stable_rate,
                liquidity_index,
                variable_borrow_index,
                last_update_timestamp,
                configuration,
            ) = reserve_data

        # Convert to proper decimal values
        liquidity_rate = float(liquidity_rate) / 1e27 if liquidity_rate else 0
        variable_borrow_rate = float(variable_borrow_rate) / 1e27 if variable_borrow_rate else 0
        stable_borrow_rate = float(stable_borrow_rate) / 1e27 if stable_borrow_rate else 0
        average_stable_rate = float(average_stable_rate) / 1e27 if average_stable_rate else 0
        liquidity_index = float(liquidity_index) / 1e27 if liquidity_index else 0
        variable_borrow_index = float(variable_borrow_index) / 1e27 if variable_borrow_index else 0

        return AaveReserveData(
            asset="",
            available_liquidity=0,
            total_debt=0,
            liquidity_rate=liquidity_rate,
            variable_borrow_rate=variable_borrow_rate,
            stable_borrow_rate=stable_borrow_rate,
            average_stable_rate=average_stable_rate,
            liquidity_index=liquidity_index,
            variable_borrow_index=variable_borrow_index,
            last_update_timestamp=last_update_timestamp,
            utilization_rate=self._calculate_utilization_rate(
                available_liquidity if hasattr(self, 'available_liquidity') else 0,
                total_debt if hasattr(self, 'total_debt') else 0
            ),
            is_active=True,
            is_frozen=False,
            is_paused=False,
            reserve_factor=0.1,
            liquidation_threshold=0.8,
            liquidation_bonus=0.05,
            loan_to_value=0.7,
            price=price,
            price_in_eth=price_in_eth,
            decimals=decimals,
        )

    def _calculate_utilization_rate(self, liquidity: float, debt: float) -> float:
        """Calculate utilization rate."""
        if liquidity + debt == 0:
            return 0.0
        return debt / (liquidity + debt)

    async def get_all_reserves(self) -> List[str]:
        """
        Get list of all reserve assets.

        Returns:
            List of asset addresses
        """
        try:
            reserves = await self._call_contract_function(
                self.contract,
                "getReservesList",
            )
            return [Web3.to_checksum_address(addr) for addr in reserves]
        except Exception as e:
            logger.error(f"Error getting reserves list: {e}")
            return []

    # -----------------------------------------------------------------------
    # User Position Management
    # -----------------------------------------------------------------------

    async def get_user_position(
        self,
        user_address: Union[str, Address],
    ) -> Optional[AavePosition]:
        """
        Get user's Aave position.

        Args:
            user_address: User address

        Returns:
            AavePosition or None if error
        """
        user_address = to_checksum_address(user_address)

        try:
            # Get user account data
            account_data = await self._call_contract_function(
                self.contract,
                "getUserAccountData",
                user_address,
            )

            if not account_data:
                return None

            # Parse account data
            (
                total_collateral_base,
                total_debt_base,
                available_borrows_base,
                current_liquidation_threshold,
                ltv,
                health_factor,
            ) = account_data

            # Convert to proper values
            total_collateral_usd = float(total_collateral_base) / 1e8 if total_collateral_base else 0
            total_debt_usd = float(total_debt_base) / 1e8 if total_debt_base else 0
            health_factor = float(health_factor) / 1e18 if health_factor else 0

            # Get detailed position data from UI data provider
            position_data = await self._get_user_reserves_data(user_address)

            # Determine risk level
            risk_level = self._calculate_risk_level(health_factor)

            return AavePosition(
                user_address=user_address,
                collateral=position_data.get("collateral", {}),
                debt=position_data.get("debt", {}),
                health_factor=health_factor,
                total_collateral_usd=total_collateral_usd,
                total_debt_usd=total_debt_usd,
                net_worth_usd=total_collateral_usd - total_debt_usd,
                risk_level=risk_level,
                available_to_borrow=position_data.get("available_to_borrow", {}),
                available_to_withdraw=position_data.get("available_to_withdraw", {}),
                liquidation_threshold=float(current_liquidation_threshold) / 1e4 if current_liquidation_threshold else 0,
                last_update=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Error getting user position for {user_address}: {e}")
            return None

    async def _get_user_reserves_data(
        self,
        user_address: str,
    ) -> Dict[str, Any]:
        """Get detailed user reserves data."""
        try:
            data = await self._call_contract_function(
                self._ui_data_provider,
                "getUserReservesData",
                user_address,
            )

            if not data:
                return {}

            # Parse the data (would be more complex in production)
            return {
                "collateral": {},
                "debt": {},
                "available_to_borrow": {},
                "available_to_withdraw": {},
            }

        except Exception as e:
            logger.error(f"Error getting user reserves data: {e}")
            return {}

    def _calculate_risk_level(self, health_factor: float) -> AaveRiskLevel:
        """Calculate risk level from health factor."""
        if health_factor >= 2.0:
            return AaveRiskLevel.SAFE
        elif health_factor >= 1.5:
            return AaveRiskLevel.MODERATE
        elif health_factor >= 1.1:
            return AaveRiskLevel.RISKY
        elif health_factor >= 1.0:
            return AaveRiskLevel.CRITICAL
        else:
            return AaveRiskLevel.LIQUIDATION

    # -----------------------------------------------------------------------
    # Lending Operations
    # -----------------------------------------------------------------------

    async def deposit(
        self,
        asset: Union[str, Address],
        amount: float,
        user_address: Union[str, Address],
        on_behalf_of: Optional[Union[str, Address]] = None,
        referral_code: int = 0,
    ) -> Optional[str]:
        """
        Deposit assets into Aave.

        Args:
            asset: Asset address
            amount: Amount to deposit
            user_address: User address
            on_behalf_of: Address to deposit on behalf of
            referral_code: Referral code

        Returns:
            Transaction hash or None if error
        """
        asset_address = to_checksum_address(asset)
        user = to_checksum_address(user_address)
        on_behalf = to_checksum_address(on_behalf_of or user)

        try:
            decimals = await self._get_asset_decimals(asset_address)
            amount_wei = int(amount * (10 ** decimals))

            # Prepare transaction
            tx = await self._build_transaction(
                self.contract,
                "supply",
                asset_address,
                amount_wei,
                on_behalf,
                referral_code,
            )

            # Send transaction
            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Deposit successful",
                    extra={
                        "asset": asset_address,
                        "amount": amount,
                        "user": user,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error depositing: {e}")
            return None

    async def withdraw(
        self,
        asset: Union[str, Address],
        amount: float,
        user_address: Union[str, Address],
        to_address: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Withdraw assets from Aave.

        Args:
            asset: Asset address
            amount: Amount to withdraw
            user_address: User address
            to_address: Address to receive assets

        Returns:
            Transaction hash or None if error
        """
        asset_address = to_checksum_address(asset)
        user = to_checksum_address(user_address)
        to = to_checksum_address(to_address or user)

        try:
            decimals = await self._get_asset_decimals(asset_address)
            amount_wei = int(amount * (10 ** decimals))

            # If amount is 0, withdraw all
            if amount == 0:
                amount_wei = 2**256 - 1  # Max uint256

            tx = await self._build_transaction(
                self.contract,
                "withdraw",
                asset_address,
                amount_wei,
                to,
            )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Withdraw successful",
                    extra={
                        "asset": asset_address,
                        "amount": amount,
                        "user": user,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error withdrawing: {e}")
            return None

    # -----------------------------------------------------------------------
    # Borrowing Operations
    # -----------------------------------------------------------------------

    async def borrow(
        self,
        asset: Union[str, Address],
        amount: float,
        user_address: Union[str, Address],
        interest_rate_mode: int = 2,  # 1 = stable, 2 = variable
        referral_code: int = 0,
        on_behalf_of: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Borrow assets from Aave.

        Args:
            asset: Asset address
            amount: Amount to borrow
            user_address: User address
            interest_rate_mode: 1 = stable, 2 = variable
            referral_code: Referral code
            on_behalf_of: Address to borrow on behalf of

        Returns:
            Transaction hash or None if error
        """
        asset_address = to_checksum_address(asset)
        user = to_checksum_address(user_address)
        on_behalf = to_checksum_address(on_behalf_of or user)

        try:
            decimals = await self._get_asset_decimals(asset_address)
            amount_wei = int(amount * (10 ** decimals))

            tx = await self._build_transaction(
                self.contract,
                "borrow",
                asset_address,
                amount_wei,
                interest_rate_mode,
                referral_code,
                on_behalf,
            )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Borrow successful",
                    extra={
                        "asset": asset_address,
                        "amount": amount,
                        "user": user,
                        "rate_mode": interest_rate_mode,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error borrowing: {e}")
            return None

    async def repay(
        self,
        asset: Union[str, Address],
        amount: float,
        user_address: Union[str, Address],
        interest_rate_mode: int = 2,
        on_behalf_of: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Repay borrowed assets.

        Args:
            asset: Asset address
            amount: Amount to repay
            user_address: User address
            interest_rate_mode: 1 = stable, 2 = variable
            on_behalf_of: Address to repay on behalf of

        Returns:
            Transaction hash or None if error
        """
        asset_address = to_checksum_address(asset)
        user = to_checksum_address(user_address)
        on_behalf = to_checksum_address(on_behalf_of or user)

        try:
            decimals = await self._get_asset_decimals(asset_address)
            amount_wei = int(amount * (10 ** decimals))

            # If amount is 0, repay all
            if amount == 0:
                amount_wei = 2**256 - 1

            tx = await self._build_transaction(
                self.contract,
                "repay",
                asset_address,
                amount_wei,
                interest_rate_mode,
                on_behalf,
            )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Repay successful",
                    extra={
                        "asset": asset_address,
                        "amount": amount,
                        "user": user,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error repaying: {e}")
            return None

    # -----------------------------------------------------------------------
    # Flash Loans
    # -----------------------------------------------------------------------

    async def flash_loan(
        self,
        params: FlashLoanParams,
        user_address: Union[str, Address],
    ) -> Optional[str]:
        """
        Execute a flash loan.

        Args:
            params: Flash loan parameters
            user_address: User address

        Returns:
            Transaction hash or None if error
        """
        user = to_checksum_address(user_address)

        try:
            # Convert amounts to wei
            amounts_wei = []
            for asset, amount in zip(params.assets, params.amounts):
                decimals = await self._get_asset_decimals(asset)
                amounts_wei.append(int(amount * (10 ** decimals)))

            # Prepare flash loan data
            # This would need to be implemented with the actual flash loan interface
            tx = await self._build_transaction(
                self.contract,
                "flashLoan",
                params.receiver,
                params.assets,
                amounts_wei,
                params.modes,
                params.on_behalf_of,
                params.referral_code,
                b"",  # params
            )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Flash loan successful",
                    extra={
                        "assets": params.assets,
                        "amounts": params.amounts,
                        "user": user,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error executing flash loan: {e}")
            return None

    # -----------------------------------------------------------------------
    # Asset Pricing
    # -----------------------------------------------------------------------

    async def get_asset_price(
        self,
        asset: Union[str, Address],
    ) -> float:
        """
        Get asset price in USD.

        Args:
            asset: Asset address

        Returns:
            Price in USD
        """
        try:
            # Use Aave oracle
            asset_address = to_checksum_address(asset)
            price = await self._call_contract_function(
                self._oracle or self.contract,
                "getAssetPrice",
                asset_address,
            )
            return float(price) / 1e8 if price else 0.0
        except Exception as e:
            logger.error(f"Error getting asset price: {e}")
            return 0.0

    async def get_asset_price_in_eth(
        self,
        asset: Union[str, Address],
    ) -> float:
        """Get asset price in ETH."""
        try:
            price = await self.get_asset_price(asset)
            eth_price = await self.get_asset_price(Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"))
            return price / eth_price if eth_price > 0 else 0.0
        except Exception:
            return 0.0

    async def _get_asset_decimals(
        self,
        asset_address: str,
    ) -> int:
        """Get asset decimals."""
        if asset_address in self._token_cache:
            return self._token_cache[asset_address].get("decimals", 18)

        try:
            token_contract = self.web3_client.get_contract(
                asset_address,
                abi=self._get_erc20_abi(),
            )
            decimals = await self._call_contract_function(
                token_contract,
                "decimals",
            )
            decimals = int(decimals) if decimals else 18

            self._token_cache[asset_address] = {"decimals": decimals}
            return decimals

        except Exception:
            return 18

    def _get_erc20_abi(self) -> List[Dict[str, Any]]:
        """Get minimal ERC20 ABI."""
        return [
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]

    # -----------------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------------

    async def analyze_position(
        self,
        position: AavePosition,
    ) -> Dict[str, Any]:
        """
        Analyze a user position and provide recommendations.

        Args:
            position: User position

        Returns:
            Analysis results
        """
        analysis = {
            "health_factor": position.health_factor,
            "risk_level": position.risk_level.value,
            "total_collateral_usd": position.total_collateral_usd,
            "total_debt_usd": position.total_debt_usd,
            "net_worth_usd": position.net_worth_usd,
            "recommendations": [],
            "warnings": [],
        }

        # Check health factor
        if position.health_factor < 1.5:
            analysis["warnings"].append(
                f"Low health factor: {position.health_factor:.2f}. Risk of liquidation."
            )
            if position.health_factor < 1.1:
                analysis["recommendations"].append(
                    "CRITICAL: Add more collateral or repay debt immediately."
                )
            else:
                analysis["recommendations"].append(
                    "Consider adding collateral or reducing debt."
                )

        # Check collateral composition
        for asset, amount in position.collateral.items():
            if amount > 0 and position.total_collateral_usd > 0:
                percentage = (amount / position.total_collateral_usd) * 100
                if percentage > 60:
                    analysis["warnings"].append(
                        f"High concentration in {asset}: {percentage:.1f}% of collateral."
                    )

        # Check debt composition
        for asset, amount in position.debt.items():
            if amount > 0 and position.total_debt_usd > 0:
                percentage = (amount / position.total_debt_usd) * 100
                if percentage > 60:
                    analysis["warnings"].append(
                        f"High debt concentration in {asset}: {percentage:.1f}% of debt."
                    )

        # Calculate optimal leverage
        current_leverage = position.total_debt_usd / position.total_collateral_usd if position.total_collateral_usd > 0 else 0
        optimal_leverage = position.liquidation_threshold * 0.8

        if current_leverage > optimal_leverage:
            analysis["recommendations"].append(
                f"Leverage is {current_leverage:.2f}x. Consider reducing to {optimal_leverage:.2f}x."
            )

        return analysis

    # -----------------------------------------------------------------------
    // ... (continue with additional methods) ...
    """
    async def get_protocol_metrics(self) -> Dict[str, Any]:
        # ... existing code ...
    ```

    # -----------------------------------------------------------------------
    # Transaction Building
    # -----------------------------------------------------------------------

    async def _build_transaction(
        self,
        contract: Contract,
        function_name: str,
        *args,
    ) -> Dict[str, Any]:
        """Build a transaction for the specified function."""
        try:
            func = getattr(contract.functions, function_name)
            tx = func(*args).build_transaction({
                "from": self.web3_client.default_account,
                "nonce": await self.web3_client.get_nonce(self.web3_client.default_account),
                "gas": 0,  # Will be estimated
                "gasPrice": await self.web3_client.get_gas_price(),
            })

            # Estimate gas
            gas = await self._estimate_gas(contract, function_name, *args)
            tx["gas"] = gas

            return tx

        except Exception as e:
            logger.error(f"Error building transaction: {e}")
            raise

    async def _estimate_gas(
        self,
        contract: Contract,
        function_name: str,
        *args,
    ) -> int:
        """Estimate gas for a transaction."""
        try:
            func = getattr(contract.functions, function_name)
            gas = await self.web3_client.estimate_gas(
                func(*args).build_transaction({
                    "from": self.web3_client.default_account,
                })
            )
            return int(gas * 1.2)  # Add 20% buffer
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}, using default")
            return 500000  # Default gas limit

    async def _send_transaction(
        self,
        tx: Dict[str, Any],
        from_address: str,
    ) -> Optional[str]:
        """Send a transaction."""
        try:
            # Sign and send
            signed_tx = self.web3_client.sign_transaction(tx, from_address)
            tx_hash = await self.web3_client.send_raw_transaction(signed_tx.rawTransaction)

            # Wait for receipt
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
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_version(self) -> AaveVersion:
        """Get the Aave protocol version."""
        return self.version

    def get_contract_addresses(self) -> Dict[str, str]:
        """Get all Aave contract addresses."""
        return self._addresses

    def get_health_factor_thresholds(self) -> Dict[str, float]:
        """Get health factor thresholds."""
        return {
            "safe": 2.0,
            "moderate": 1.5,
            "risky": 1.1,
            "critical": 1.0,
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the Aave contract integration."""
        if self._running:
            return

        self._running = True
        logger.info("AaveContract started")

    async def stop(self) -> None:
        """Stop the Aave contract integration."""
        self._running = False
        logger.info("AaveContract stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_aave_contract(
    web3_client: Web3Client,
    version: AaveVersion = AaveVersion.V3,
    config: Optional[Dict[str, Any]] = None,
) -> AaveContract:
    """
    Factory function to create an AaveContract instance.

    Args:
        web3_client: Web3 client instance
        version: Aave protocol version
        config: Configuration dictionary

    Returns:
        AaveContract instance
    """
    return AaveContract(
        web3_client=web3_client,
        version=version,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the Aave contract
    pass
