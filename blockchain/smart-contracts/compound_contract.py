# blockchain/smart-contracts/compound_contract.py
# NEXUS AI TRADING SYSTEM - Compound Protocol Smart Contract Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Compound Protocol Smart Contract Integration for NEXUS AI Trading System.
Provides comprehensive interaction with Compound V2 and V3 protocols including:
- Supply and withdraw assets
- Borrow and repay assets
- cToken interactions
- Comptroller operations
- Liquidation monitoring
- Interest rate analysis
- Collateral management
- Governance participation
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
from eth_account import Account
from eth_typing import Address, ChecksumAddress

# NEXUS Imports
from blockchain.smart_contracts.base_contract import BaseContract
from blockchain.web3.web3_client import Web3Client
from shared.constants.error_constants import ErrorSeverity
from shared.helpers.crypto_helpers import to_checksum_address
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.compound")


# ============================================================================
# Enums & Constants
# ============================================================================

class CompoundVersion(str, Enum):
    """Compound protocol versions."""
    V2 = "v2"
    V3 = "v3"


class CompoundAction(str, Enum):
    """Compound protocol actions."""
    SUPPLY = "supply"
    WITHDRAW = "withdraw"
    BORROW = "borrow"
    REPAY = "repay"
    LIQUIDATE = "liquidate"
    ENTER_MARKET = "enter_market"
    EXIT_MARKET = "exit_market"
    CLAIM_COMP = "claim_comp"
    DELEGATE = "delegate"


class CompoundRiskLevel(str, Enum):
    """Risk levels for Compound positions."""
    SAFE = "safe"          # Collateral ratio > 2.0
    MODERATE = "moderate"   # Collateral ratio 1.5 - 2.0
    RISKY = "risky"        # Collateral ratio 1.1 - 1.5
    CRITICAL = "critical"   # Collateral ratio 1.0 - 1.1
    LIQUIDATION = "liquidation"  # Collateral ratio < 1.0


@dataclass
class CTokenData:
    """cToken data structure."""
    address: str
    underlying: str
    underlying_name: str
    underlying_symbol: str
    underlying_decimals: int
    exchange_rate: float
    supply_rate: float
    borrow_rate: float
    cash: float
    total_borrows: float
    total_supply: float
    reserve_factor: float
    collateral_factor: float
    liquidation_threshold: float
    liquidation_bonus: float
    price: float
    price_usd: float
    is_listed: bool
    is_collateral: bool
    accrual_block_timestamp: int
    market_health: float
    utilization_rate: float


@dataclass
class CompoundPosition:
    """Compound user position."""
    user_address: str
    supplied: Dict[str, float]
    borrowed: Dict[str, float]
    collateral: Dict[str, float]
    total_supplied_usd: float
    total_borrowed_usd: float
    net_worth_usd: float
    collateral_ratio: float
    risk_level: CompoundRiskLevel
    liquidation_price: Dict[str, float]
    available_to_borrow: Dict[str, float]
    available_to_withdraw: Dict[str, float]
    comp_earned: float
    comp_unclaimed: float
    last_update: datetime
    markets_entered: List[str]


@dataclass
class CompoundTransaction:
    """Compound transaction details."""
    tx_hash: str
    action: CompoundAction
    c_token: str
    underlying: str
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
class InterestRateModel:
    """Compound interest rate model data."""
    base_rate_per_year: float
    multiplier_per_year: float
    jump_multiplier_per_year: float
    kink: float
    utilization_rate: float
    supply_rate: float
    borrow_rate: float
    reserve_factor: float


# ============================================================================
# Compound Contract Integration
# ============================================================================

class CompoundContract(BaseContract):
    """
    Compound Protocol Smart Contract Integration.
    Supports both V2 and V3 protocols.
    """

    # Compound V2 contract addresses (mainnet)
    V2_ADDRESSES = {
        "comptroller": "0x3d9819210A31b4961b30EF54bE2aeD79B9Bb9f67",
        "price_oracle": "0x671F9ed1Ee765Ed3F768375119FdA19539564c29",
        "comp_token": "0xc00e94Cb662C3520282E6f5717214004A7f26888",
        "governance": "0xc0Da02939E1441F497fd74F78cE7Decb17B66529",
        "maximillion": "0x5B7B811c5E7c0C033923D025C2DeFd328a0339eA",
        "ceth": "0x4Ddc2D193948926D02f9B1fE9e1daa0718270ED5",
        "cuni": "0x35A18000230DA775CAc24873d00Ff85BccdeD550",
    }

    # Common cToken addresses (mainnet)
    CTOKEN_ADDRESSES = {
        "ETH": "0x4Ddc2D193948926D02f9B1fE9e1daa0718270ED5",
        "DAI": "0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643",
        "USDC": "0x39AA39c021dfbaE8faC545936693aC917d5E7563",
        "USDT": "0xf650C3d88D12dB855b8bf7D11Be6C55A4e07dCC9",
        "WBTC": "0xC11b1268C1A384e55C48c2391d8d480264A3A7F4",
        "UNI": "0x35A18000230DA775CAc24873d00Ff85BccdeD550",
        "COMP": "0x70e36f6BF80a52b3B46b3aF8e106CC0ed743E8e4",
        "LINK": "0xFacE851A4921ce59e912d1932998CE0156f0AeE0",
        "AAVE": "0xE65cdB6479C6AD94A4c85A506daa1eBF6Ae0Df10",
        "MKR": "0x95b4eF2869eBD94BEb4eEE400A99824BF5DC325b",
        "SNX": "0x35A18000230DA775CAc24873d00Ff85BccdeD550",
        "YFI": "0x3a3A65aAb0dd2A17E3F1947bA16138cd37d08c04",
        "ZRX": "0xB3319f5D18Bc0D84dD1b4825Dcde5d5f7266d407",
        "BAT": "0x6C8c6b02E7b2BE14d4fA6022Dfd6d75921D90E4E",
        "REP": "0x158079Ee67Fce2f58472A96584A73C7Ab9AC95c1",
        "SAI": "0xF5DCe57282A584D2746FaF1593d3121Fcac444dC",
    }

    # Minimal cToken ABI
    CTOKEN_ABI = [
        {
            "constant": True,
            "inputs": [],
            "name": "underlying",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "exchangeRateStored",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "supplyRatePerBlock",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "borrowRatePerBlock",
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
        {
            "constant": True,
            "inputs": [],
            "name": "totalBorrows",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "getCash",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "reserveFactorMantissa",
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
            "inputs": [{"name": "account", "type": "address"}],
            "name": "borrowBalanceStored",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [{"name": "minter", "type": "address"}],
            "name": "mint",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [{"name": "amount", "type": "uint256"}],
            "name": "redeem",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [{"name": "borrowAmount", "type": "uint256"}],
            "name": "borrow",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [{"name": "borrowAmount", "type": "uint256"}],
            "name": "repayBorrow",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "borrower", "type": "address"},
                {"name": "repayAmount", "type": "uint256"},
                {"name": "cTokenCollateral", "type": "address"}
            ],
            "name": "liquidateBorrow",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
    ]

    # Comptroller ABI (minimal)
    COMPTROLLER_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "account", "type": "address"}],
            "name": "getAccountLiquidity",
            "outputs": [
                {"name": "err", "type": "uint256"},
                {"name": "liquidity", "type": "uint256"},
                {"name": "shortfall", "type": "uint256"},
            ],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "getAllMarkets",
            "outputs": [{"name": "", "type": "address[]"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "cToken", "type": "address"}],
            "name": "markets",
            "outputs": [
                {"name": "isListed", "type": "bool"},
                {"name": "collateralFactorMantissa", "type": "uint256"},
                {"name": "isComped", "type": "bool"},
            ],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "account", "type": "address"}],
            "name": "getAssetsIn",
            "outputs": [{"name": "", "type": "address[]"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [{"name": "cToken", "type": "address"}],
            "name": "enterMarkets",
            "outputs": [{"name": "", "type": "uint256[]"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [{"name": "cTokenAddress", "type": "address"}],
            "name": "exitMarket",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
    ]

    def __init__(
        self,
        web3_client: Web3Client,
        version: CompoundVersion = CompoundVersion.V2,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Compound contract integration.

        Args:
            web3_client: Web3 client instance
            version: Compound protocol version
            config: Configuration dictionary
        """
        super().__init__(
            web3_client=web3_client,
            contract_name="Compound",
            contract_address=self._get_contract_address(version),
            abi=self.COMPTROLLER_ABI,
            config=config,
        )

        self.version = version
        self._addresses = self.V2_ADDRESSES

        # Initialize sub-contracts
        self._comptroller = self.contract
        self._ctoken_cache: Dict[str, Contract] = {}
        self._ctoken_data_cache: Dict[str, CTokenData] = {}
        self._last_cache_update: datetime = datetime.utcnow() - timedelta(minutes=5)

        logger.info(
            f"CompoundContract initialized",
            extra={
                "version": version.value,
                "comptroller_address": self.contract_address,
                "chain": web3_client.chain_name,
            }
        )

    def _get_contract_address(self, version: CompoundVersion) -> str:
        """Get the appropriate contract address for the version."""
        if version == CompoundVersion.V3:
            # V3 addresses would go here
            return self.V2_ADDRESSES["comptroller"]
        return self.V2_ADDRESSES["comptroller"]

    # -----------------------------------------------------------------------
    # cToken Management
    # -----------------------------------------------------------------------

    async def get_ctoken_contract(
        self,
        ctoken_address: Union[str, Address],
    ) -> Optional[Contract]:
        """
        Get cToken contract instance.

        Args:
            ctoken_address: cToken address

        Returns:
            Contract instance or None if error
        """
        ctoken_address = to_checksum_address(ctoken_address)

        if ctoken_address in self._ctoken_cache:
            return self._ctoken_cache[ctoken_address]

        try:
            contract = self.web3_client.get_contract(
                ctoken_address,
                abi=self.CTOKEN_ABI,
            )
            self._ctoken_cache[ctoken_address] = contract
            return contract

        except Exception as e:
            logger.error(f"Error getting cToken contract: {e}")
            return None

    async def get_ctoken_data(
        self,
        ctoken_address: Union[str, Address],
        force_refresh: bool = False,
    ) -> Optional[CTokenData]:
        """
        Get cToken data.

        Args:
            ctoken_address: cToken address
            force_refresh: Force refresh cache

        Returns:
            CTokenData or None if error
        """
        ctoken_address = to_checksum_address(ctoken_address)

        if not force_refresh and ctoken_address in self._ctoken_data_cache:
            return self._ctoken_data_cache[ctoken_address]

        try:
            ctoken = await self.get_ctoken_contract(ctoken_address)
            if not ctoken:
                return None

            # Get underlying address
            underlying = await self._call_contract_function(ctoken, "underlying")
            underlying = Web3.to_checksum_address(underlying) if underlying else None

            # Get exchange rate
            exchange_rate = await self._call_contract_function(ctoken, "exchangeRateStored")
            exchange_rate = float(exchange_rate) / 1e18 if exchange_rate else 0

            # Get rates
            supply_rate = await self._call_contract_function(ctoken, "supplyRatePerBlock")
            borrow_rate = await self._call_contract_function(ctoken, "borrowRatePerBlock")
            supply_rate = self._rate_per_block_to_apy(supply_rate)
            borrow_rate = self._rate_per_block_to_apy(borrow_rate)

            # Get supply and borrow amounts
            total_supply = await self._call_contract_function(ctoken, "totalSupply")
            total_borrows = await self._call_contract_function(ctoken, "totalBorrows")
            cash = await self._call_contract_function(ctoken, "getCash")

            total_supply = float(total_supply) / 1e18 if total_supply else 0
            total_borrows = float(total_borrows) / 1e18 if total_borrows else 0
            cash = float(cash) / 1e18 if cash else 0

            # Get reserve factor
            reserve_factor = await self._call_contract_function(ctoken, "reserveFactorMantissa")
            reserve_factor = float(reserve_factor) / 1e18 if reserve_factor else 0

            # Get market info from comptroller
            market_info = await self._call_contract_function(
                self._comptroller,
                "markets",
                ctoken_address,
            )

            is_listed = market_info[0] if market_info else False
            collateral_factor = float(market_info[1]) / 1e18 if market_info else 0

            # Get price (would use oracle in production)
            price = await self.get_ctoken_price(ctoken_address)
            price_usd = price * self._get_eth_price() if self.version == CompoundVersion.V2 else price

            # Get underlying info
            underlying_info = await self._get_underlying_info(underlying) if underlying else {}

            # Calculate utilization rate
            utilization_rate = self._calculate_utilization_rate(cash, total_borrows)

            # Calculate market health
            market_health = self._calculate_market_health(
                cash,
                total_borrows,
                total_supply,
                collateral_factor,
            )

            data = CTokenData(
                address=ctoken_address,
                underlying=underlying or "",
                underlying_name=underlying_info.get("name", "Unknown"),
                underlying_symbol=underlying_info.get("symbol", "Unknown"),
                underlying_decimals=underlying_info.get("decimals", 18),
                exchange_rate=exchange_rate,
                supply_rate=supply_rate,
                borrow_rate=borrow_rate,
                cash=cash,
                total_borrows=total_borrows,
                total_supply=total_supply,
                reserve_factor=reserve_factor,
                collateral_factor=collateral_factor,
                liquidation_threshold=0.85,  # Would get from config
                liquidation_bonus=0.05,  # Would get from config
                price=price,
                price_usd=price_usd,
                is_listed=is_listed,
                is_collateral=collateral_factor > 0,
                accrual_block_timestamp=int(datetime.utcnow().timestamp()),
                market_health=market_health,
                utilization_rate=utilization_rate,
            )

            self._ctoken_data_cache[ctoken_address] = data
            self._last_cache_update = datetime.utcnow()

            return data

        except Exception as e:
            logger.error(f"Error getting cToken data for {ctoken_address}: {e}")
            return None

    async def _get_underlying_info(
        self,
        underlying_address: str,
    ) -> Dict[str, Any]:
        """Get underlying token information."""
        try:
            if not underlying_address:
                return {}

            token_contract = self.web3_client.get_contract(
                underlying_address,
                abi=self._get_erc20_abi(),
            )

            name = await self._call_contract_function(token_contract, "name")
            symbol = await self._call_contract_function(token_contract, "symbol")
            decimals = await self._call_contract_function(token_contract, "decimals")

            return {
                "name": name or "Unknown",
                "symbol": symbol or "Unknown",
                "decimals": int(decimals) if decimals else 18,
            }

        except Exception as e:
            logger.error(f"Error getting underlying info: {e}")
            return {}

    def _get_erc20_abi(self) -> List[Dict[str, Any]]:
        """Get minimal ERC20 ABI."""
        return [
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
        ]

    def _calculate_utilization_rate(self, cash: float, borrows: float) -> float:
        """Calculate utilization rate."""
        if cash + borrows == 0:
            return 0.0
        return borrows / (cash + borrows)

    def _calculate_market_health(
        self,
        cash: float,
        borrows: float,
        supply: float,
        collateral_factor: float,
    ) -> float:
        """Calculate market health score."""
        if supply == 0:
            return 1.0

        utilization = self._calculate_utilization_rate(cash, borrows)
        score = 1.0 - utilization

        # Adjust for collateral factor
        score *= collateral_factor

        return max(0.0, min(1.0, score))

    def _rate_per_block_to_apy(self, rate: Optional[int]) -> float:
        """Convert rate per block to APY."""
        if not rate:
            return 0.0

        # Approximate blocks per year (assuming 15s blocks)
        blocks_per_year = 365 * 24 * 60 * 60 / 15
        rate_per_block = float(rate) / 1e18
        return (1 + rate_per_block) ** blocks_per_year - 1

    # -----------------------------------------------------------------------
    # Price Oracle
    # -----------------------------------------------------------------------

    async def get_ctoken_price(
        self,
        ctoken_address: Union[str, Address],
    ) -> float:
        """
        Get cToken price.

        Args:
            ctoken_address: cToken address

        Returns:
            Price in ETH
        """
        try:
            # Would use Compound price oracle
            # For now, get exchange rate
            ctoken = await self.get_ctoken_contract(ctoken_address)
            if not ctoken:
                return 0.0

            exchange_rate = await self._call_contract_function(ctoken, "exchangeRateStored")
            return float(exchange_rate) / 1e18 if exchange_rate else 0.0

        except Exception as e:
            logger.error(f"Error getting cToken price: {e}")
            return 0.0

    def _get_eth_price(self) -> float:
        """Get ETH price in USD."""
        # Would use price feed in production
        return 3500.0

    # -----------------------------------------------------------------------
    # User Position Management
    # -----------------------------------------------------------------------

    async def get_user_position(
        self,
        user_address: Union[str, Address],
    ) -> Optional[CompoundPosition]:
        """
        Get user's Compound position.

        Args:
            user_address: User address

        Returns:
            CompoundPosition or None if error
        """
        user_address = to_checksum_address(user_address)

        try:
            # Get account liquidity
            liquidity_data = await self._call_contract_function(
                self._comptroller,
                "getAccountLiquidity",
                user_address,
            )

            if not liquidity_data:
                return None

            err, liquidity, shortfall = liquidity_data

            # Get markets user has entered
            markets = await self._call_contract_function(
                self._comptroller,
                "getAssetsIn",
                user_address,
            )

            # Get positions for each market
            supplied = {}
            borrowed = {}
            collateral = {}
            available_to_borrow = {}
            available_to_withdraw = {}
            liquidation_price = {}

            total_supplied_usd = 0
            total_borrowed_usd = 0

            for market in markets:
                ctoken = await self.get_ctoken_contract(market)
                if not ctoken:
                    continue

                # Get user balance
                balance = await self._call_contract_function(
                    ctoken,
                    "balanceOf",
                    user_address,
                )
                balance = float(balance) / 1e18 if balance else 0

                # Get borrow balance
                borrow_balance = await self._call_contract_function(
                    ctoken,
                    "borrowBalanceStored",
                    user_address,
                )
                borrow_balance = float(borrow_balance) / 1e18 if borrow_balance else 0

                # Get market data
                ctoken_data = await self.get_ctoken_data(market)
                if not ctoken_data:
                    continue

                # Calculate USD values
                underlying_balance = balance * ctoken_data.exchange_rate
                supplied_usd = underlying_balance * ctoken_data.price_usd
                borrowed_usd = borrow_balance * ctoken_data.price_usd

                if underlying_balance > 0:
                    supplied[ctoken_data.underlying_symbol] = underlying_balance
                    total_supplied_usd += supplied_usd

                if borrow_balance > 0:
                    borrowed[ctoken_data.underlying_symbol] = borrow_balance
                    total_borrowed_usd += borrowed_usd

                if ctoken_data.is_collateral and balance > 0:
                    collateral[ctoken_data.underlying_symbol] = underlying_balance

                # Calculate available to borrow/withdraw
                # This is a simplified calculation
                if ctoken_data.is_collateral:
                    avail_borrow = (underlying_balance * ctoken_data.collateral_factor * 0.8) - borrow_balance
                    if avail_borrow > 0:
                        available_to_borrow[ctoken_data.underlying_symbol] = avail_borrow

                if borrow_balance == 0:
                    available_to_withdraw[ctoken_data.underlying_symbol] = underlying_balance

                # Liquidation price (simplified)
                if borrow_balance > 0:
                    l_price = (underlying_balance / borrow_balance) * ctoken_data.price * 0.8
                    liquidation_price[ctoken_data.underlying_symbol] = l_price

            # Calculate collateral ratio
            collateral_ratio = total_supplied_usd / total_borrowed_usd if total_borrowed_usd > 0 else 0

            # Determine risk level
            risk_level = self._calculate_risk_level(collateral_ratio)

            # Get COMP earned
            comp_earned = await self._get_comp_earned(user_address)

            return CompoundPosition(
                user_address=user_address,
                supplied=supplied,
                borrowed=borrowed,
                collateral=collateral,
                total_supplied_usd=total_supplied_usd,
                total_borrowed_usd=total_borrowed_usd,
                net_worth_usd=total_supplied_usd - total_borrowed_usd,
                collateral_ratio=collateral_ratio,
                risk_level=risk_level,
                liquidation_price=liquidation_price,
                available_to_borrow=available_to_borrow,
                available_to_withdraw=available_to_withdraw,
                comp_earned=comp_earned,
                comp_unclaimed=0,
                last_update=datetime.utcnow(),
                markets_entered=[Web3.to_checksum_address(m) for m in markets],
            )

        except Exception as e:
            logger.error(f"Error getting user position for {user_address}: {e}")
            return None

    async def _get_comp_earned(self, user_address: str) -> float:
        """Get COMP tokens earned by user."""
        try:
            # Would call COMP token contract
            return 0.0
        except Exception:
            return 0.0

    def _calculate_risk_level(self, collateral_ratio: float) -> CompoundRiskLevel:
        """Calculate risk level from collateral ratio."""
        if collateral_ratio >= 2.0:
            return CompoundRiskLevel.SAFE
        elif collateral_ratio >= 1.5:
            return CompoundRiskLevel.MODERATE
        elif collateral_ratio >= 1.1:
            return CompoundRiskLevel.RISKY
        elif collateral_ratio >= 1.0:
            return CompoundRiskLevel.CRITICAL
        else:
            return CompoundRiskLevel.LIQUIDATION

    # -----------------------------------------------------------------------
    # Supply Operations
    # -----------------------------------------------------------------------

    async def supply(
        self,
        ctoken_address: Union[str, Address],
        amount: float,
        user_address: Union[str, Address],
    ) -> Optional[str]:
        """
        Supply assets to Compound.

        Args:
            ctoken_address: cToken address
            amount: Amount to supply
            user_address: User address

        Returns:
            Transaction hash or None if error
        """
        ctoken_address = to_checksum_address(ctoken_address)
        user = to_checksum_address(user_address)

        try:
            ctoken = await self.get_ctoken_contract(ctoken_address)
            if not ctoken:
                return None

            # Get underlying decimals
            ctoken_data = await self.get_ctoken_data(ctoken_address)
            if not ctoken_data:
                return None

            decimals = ctoken_data.underlying_decimals
            amount_wei = int(amount * (10 ** decimals))

            # Build and send transaction
            tx = await self._build_transaction(
                ctoken,
                "mint",
                amount_wei,
            )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Supply successful",
                    extra={
                        "ctoken": ctoken_address,
                        "amount": amount,
                        "user": user,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error supplying: {e}")
            return None

    async def withdraw(
        self,
        ctoken_address: Union[str, Address],
        amount: float,
        user_address: Union[str, Address],
    ) -> Optional[str]:
        """
        Withdraw assets from Compound.

        Args:
            ctoken_address: cToken address
            amount: Amount to withdraw
            user_address: User address

        Returns:
            Transaction hash or None if error
        """
        ctoken_address = to_checksum_address(ctoken_address)
        user = to_checksum_address(user_address)

        try:
            ctoken = await self.get_ctoken_contract(ctoken_address)
            if not ctoken:
                return None

            # Get underlying decimals
            ctoken_data = await self.get_ctoken_data(ctoken_address)
            if not ctoken_data:
                return None

            decimals = ctoken_data.underlying_decimals

            # If amount is 0, withdraw all
            amount_wei = int(amount * (10 ** decimals)) if amount > 0 else 0
            if amount == 0:
                # Redeem all
                tx = await self._build_transaction(ctoken, "redeem", 2**256 - 1)
            else:
                tx = await self._build_transaction(
                    ctoken,
                    "redeem",
                    amount_wei,
                )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Withdraw successful",
                    extra={
                        "ctoken": ctoken_address,
                        "amount": amount if amount > 0 else "all",
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
        ctoken_address: Union[str, Address],
        amount: float,
        user_address: Union[str, Address],
    ) -> Optional[str]:
        """
        Borrow assets from Compound.

        Args:
            ctoken_address: cToken address
            amount: Amount to borrow
            user_address: User address

        Returns:
            Transaction hash or None if error
        """
        ctoken_address = to_checksum_address(ctoken_address)
        user = to_checksum_address(user_address)

        try:
            ctoken = await self.get_ctoken_contract(ctoken_address)
            if not ctoken:
                return None

            # Get underlying decimals
            ctoken_data = await self.get_ctoken_data(ctoken_address)
            if not ctoken_data:
                return None

            decimals = ctoken_data.underlying_decimals
            amount_wei = int(amount * (10 ** decimals))

            # Build transaction
            tx = await self._build_transaction(
                ctoken,
                "borrow",
                amount_wei,
            )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Borrow successful",
                    extra={
                        "ctoken": ctoken_address,
                        "amount": amount,
                        "user": user,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error borrowing: {e}")
            return None

    async def repay(
        self,
        ctoken_address: Union[str, Address],
        amount: float,
        user_address: Union[str, Address],
    ) -> Optional[str]:
        """
        Repay borrowed assets.

        Args:
            ctoken_address: cToken address
            amount: Amount to repay
            user_address: User address

        Returns:
            Transaction hash or None if error
        """
        ctoken_address = to_checksum_address(ctoken_address)
        user = to_checksum_address(user_address)

        try:
            ctoken = await self.get_ctoken_contract(ctoken_address)
            if not ctoken:
                return None

            # Get underlying decimals
            ctoken_data = await self.get_ctoken_data(ctoken_address)
            if not ctoken_data:
                return None

            decimals = ctoken_data.underlying_decimals

            # If amount is 0, repay all
            amount_wei = int(amount * (10 ** decimals)) if amount > 0 else 0
            if amount == 0:
                # Repay all
                tx = await self._build_transaction(ctoken, "repayBorrow", 2**256 - 1)
            else:
                tx = await self._build_transaction(
                    ctoken,
                    "repayBorrow",
                    amount_wei,
                )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Repay successful",
                    extra={
                        "ctoken": ctoken_address,
                        "amount": amount if amount > 0 else "all",
                        "user": user,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error repaying: {e}")
            return None

    # -----------------------------------------------------------------------
    # Market Management
    # -----------------------------------------------------------------------

    async def enter_market(
        self,
        ctoken_addresses: List[Union[str, Address]],
        user_address: Union[str, Address],
    ) -> List[str]:
        """
        Enter one or more markets.

        Args:
            ctoken_addresses: List of cToken addresses
            user_address: User address

        Returns:
            List of transaction hashes
        """
        user = to_checksum_address(user_address)
        tx_hashes = []

        for ctoken in ctoken_addresses:
            ctoken_address = to_checksum_address(ctoken)

            try:
                tx = await self._build_transaction(
                    self._comptroller,
                    "enterMarkets",
                    [ctoken_address],
                )

                tx_hash = await self._send_transaction(tx, user)

                if tx_hash:
                    tx_hashes.append(tx_hash)
                    logger.info(
                        f"Entered market: {ctoken_address}",
                        extra={"user": user, "tx_hash": tx_hash}
                    )

            except Exception as e:
                logger.error(f"Error entering market {ctoken_address}: {e}")

        return tx_hashes

    async def exit_market(
        self,
        ctoken_address: Union[str, Address],
        user_address: Union[str, Address],
    ) -> Optional[str]:
        """
        Exit a market.

        Args:
            ctoken_address: cToken address
            user_address: User address

        Returns:
            Transaction hash or None if error
        """
        ctoken_address = to_checksum_address(ctoken_address)
        user = to_checksum_address(user_address)

        try:
            tx = await self._build_transaction(
                self._comptroller,
                "exitMarket",
                ctoken_address,
            )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Exited market: {ctoken_address}",
                    extra={"user": user, "tx_hash": tx_hash}
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error exiting market: {e}")
            return None

    # -----------------------------------------------------------------------
    # Liquidation Operations
    # -----------------------------------------------------------------------

    async def liquidate(
        self,
        borrower: Union[str, Address],
        ctoken_collateral: Union[str, Address],
        ctoken_debt: Union[str, Address],
        repay_amount: float,
        user_address: Union[str, Address],
    ) -> Optional[str]:
        """
        Liquidate a borrower.

        Args:
            borrower: Borrower address
            ctoken_collateral: cToken address for collateral
            ctoken_debt: cToken address for debt
            repay_amount: Amount to repay
            user_address: User address performing liquidation

        Returns:
            Transaction hash or None if error
        """
        borrower = to_checksum_address(borrower)
        ctoken_collateral = to_checksum_address(ctoken_collateral)
        ctoken_debt = to_checksum_address(ctoken_debt)
        user = to_checksum_address(user_address)

        try:
            ctoken = await self.get_ctoken_contract(ctoken_debt)
            if not ctoken:
                return None

            # Get underlying decimals
            ctoken_data = await self.get_ctoken_data(ctoken_debt)
            if not ctoken_data:
                return None

            decimals = ctoken_data.underlying_decimals
            amount_wei = int(repay_amount * (10 ** decimals))

            tx = await self._build_transaction(
                ctoken,
                "liquidateBorrow",
                borrower,
                amount_wei,
                ctoken_collateral,
            )

            tx_hash = await self._send_transaction(tx, user)

            if tx_hash:
                logger.info(
                    f"Liquidation successful",
                    extra={
                        "borrower": borrower,
                        "collateral": ctoken_collateral,
                        "debt": ctoken_debt,
                        "amount": repay_amount,
                        "user": user,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error liquidating: {e}")
            return None

    # -----------------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------------

    async def analyze_position(
        self,
        position: CompoundPosition,
    ) -> Dict[str, Any]:
        """
        Analyze a user position and provide recommendations.

        Args:
            position: User position

        Returns:
            Analysis results
        """
        analysis = {
            "collateral_ratio": position.collateral_ratio,
            "risk_level": position.risk_level.value,
            "total_supplied_usd": position.total_supplied_usd,
            "total_borrowed_usd": position.total_borrowed_usd,
            "net_worth_usd": position.net_worth_usd,
            "recommendations": [],
            "warnings": [],
            "opportunities": [],
        }

        # Check collateral ratio
        if position.collateral_ratio < 1.5:
            analysis["warnings"].append(
                f"Low collateral ratio: {position.collateral_ratio:.2f}. Risk of liquidation."
            )
            if position.collateral_ratio < 1.1:
                analysis["recommendations"].append(
                    "CRITICAL: Add more collateral or repay debt immediately."
                )
            else:
                analysis["recommendations"].append(
                    "Consider adding collateral or reducing debt."
                )

        # Check diversification
        if len(position.supplied) < 2:
            analysis["recommendations"].append(
                "Consider diversifying supplied assets."
            )

        if len(position.borrowed) > 0:
            # Check interest rates
            for asset in position.borrowed:
                # Would get current interest rate
                analysis["opportunities"].append(
                    f"Monitor {asset} borrow rate for potential refinancing."
                )

        # Check for arbitrage opportunities
        if position.available_to_borrow:
            for asset, amount in position.available_to_borrow.items():
                if amount > 1000:  # Minimum threshold
                    analysis["opportunities"].append(
                        f"Available to borrow ${amount:.2f} of {asset} at current rates."
                    )

        # Check for COMP rewards
        if position.comp_earned > 0:
            analysis["opportunities"].append(
                f"Unclaimed COMP rewards: {position.comp_earned:.4f} COMP."
            )

        return analysis

    # -----------------------------------------------------------------------
    # Interest Rate Analysis
    # -----------------------------------------------------------------------

    async def get_interest_rate_model(
        self,
        ctoken_address: Union[str, Address],
    ) -> Optional[InterestRateModel]:
        """
        Get interest rate model for a cToken.

        Args:
            ctoken_address: cToken address

        Returns:
            InterestRateModel or None if error
        """
        ctoken_address = to_checksum_address(ctoken_address)

        try:
            ctoken_data = await self.get_ctoken_data(ctoken_address)
            if not ctoken_data:
                return None

            # In production, would get these from the actual rate model contract
            # Using reasonable defaults for now
            return InterestRateModel(
                base_rate_per_year=0.02,
                multiplier_per_year=0.08,
                jump_multiplier_per_year=0.5,
                kink=0.8,
                utilization_rate=ctoken_data.utilization_rate,
                supply_rate=ctoken_data.supply_rate,
                borrow_rate=ctoken_data.borrow_rate,
                reserve_factor=ctoken_data.reserve_factor,
            )

        except Exception as e:
            logger.error(f"Error getting interest rate model: {e}")
            return None

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
                "gas": 0,
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
            return int(gas * 1.2)
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}, using default")
            return 500000

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
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_version(self) -> CompoundVersion:
        """Get the Compound protocol version."""
        return self.version

    def get_all_ctokens(self) -> List[str]:
        """Get all cToken addresses."""
        return list(self.CTOKEN_ADDRESSES.values())

    def get_ctoken_address_for_underlying(
        self,
        underlying_symbol: str,
    ) -> Optional[str]:
        """Get cToken address for an underlying token symbol."""
        return self.CTOKEN_ADDRESSES.get(underlying_symbol.upper())

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
        """Start the Compound contract integration."""
        if self._running:
            return

        self._running = True
        logger.info("CompoundContract started")

    async def stop(self) -> None:
        """Stop the Compound contract integration."""
        self._running = False
        logger.info("CompoundContract stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_compound_contract(
    web3_client: Web3Client,
    version: CompoundVersion = CompoundVersion.V2,
    config: Optional[Dict[str, Any]] = None,
) -> CompoundContract:
    """
    Factory function to create a CompoundContract instance.

    Args:
        web3_client: Web3 client instance
        version: Compound protocol version
        config: Configuration dictionary

    Returns:
        CompoundContract instance
    """
    return CompoundContract(
        web3_client=web3_client,
        version=version,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the Compound contract
    pass
