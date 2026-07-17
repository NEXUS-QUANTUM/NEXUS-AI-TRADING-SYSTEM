# blockchain/staking/eth_staking.py
# NEXUS AI TRADING SYSTEM - Ethereum Staking Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Ethereum Staking Integration for NEXUS AI Trading System.
Provides comprehensive staking operations for Ethereum including:
- ETH2.0 Beacon Chain staking
- Solo staking (32 ETH validator)
- Liquid staking (stETH, rETH, wstETH)
- Rocket Pool integration
- Lido integration
- Staking pools
- Validator management
- Reward claiming
- APR/APY calculations
- Withdrawal management
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
from web3 import Web3

# NEXUS Imports
from blockchain.staking.base_staking import BaseStaking, StakingProvider, StakingStatus, ValidatorStatus, ValidatorInfo
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.staking.eth")


# ============================================================================
# Enums & Constants
# ============================================================================

class ETHStakingType(str, Enum):
    """Ethereum staking types."""
    SOLO = "solo"              # Solo validator (32 ETH)
    LIQUID = "liquid"          # Liquid staking (stETH, rETH)
    POOL = "pool"              # Staking pool
    ROCKET_POOL = "rocket_pool"  # Rocket Pool
    LIDO = "lido"              # Lido
    STAKE_WISE = "stake_wise"   # StakeWise


class ETHValidatorStatus(str, Enum):
    """Ethereum validator status."""
    PENDING = "pending"
    ACTIVE = "active"
    EXITING = "exiting"
    SLASHED = "slashed"
    WITHDRAWN = "withdrawn"


@dataclass
class ETHValidator:
    """Ethereum validator information."""
    index: int
    pubkey: str
    balance: float
    effective_balance: float
    status: ETHValidatorStatus
    activation_epoch: int
    exit_epoch: int
    withdrawable_epoch: int
    validator_apy: float
    commission: float
    is_active: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ETHStakingPosition:
    """Ethereum staking position."""
    total_staked: float
    total_rewards: float
    total_value_usd: float
    validators: List[ETHValidator]
    liquid_staked: Dict[str, float]
    staking_type: ETHStakingType
    average_apy: float
    daily_rewards: float
    weekly_rewards: float
    monthly_rewards: float
    status: StakingStatus = StakingStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ETHStakingStats:
    """Ethereum staking statistics."""
    total_eth_staked: float
    total_validators: int
    active_validators: int
    average_apy: float
    min_apy: float
    max_apy: float
    median_apy: float
    staking_rate: float
    total_staked_usd: float
    liquid_staking_tvl: float
    beacon_chain_validators: int
    avg_validator_balance: float
    last_updated: datetime


@dataclass
class LiquidStakingProtocol:
    """Liquid staking protocol information."""
    name: str
    address: str
    symbol: str
    apy: float
    tvl: float
    fee: float
    is_active: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Ethereum Staking Integration
# ============================================================================

class ETHStaking(BaseStaking):
    """
    Ethereum Staking Integration.
    Provides comprehensive staking operations for Ethereum.
    """

    # Ethereum mainnet addresses
    CONTRACT_ADDRESSES = {
        "beacon_deposit": "0x00000000219ab540356cBB839Cbe05303d7705Fa",
        "lido_steth": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
        "rocket_pool": "0x3bE9659ECd5f230Fd7fcA60aF4D6620cBd5fD120",
        "stake_wise": "0xfE6EfD1676b41C7C1648b295BD2C5FdEe9b5F3A8",
        "stader": "0xcf5EA1b38380f6aF39068375516Daf40Ed70D299",
    }

    # Liquid staking protocols
    LIQUID_PROTOCOLS = {
        "stETH": {
            "address": CONTRACT_ADDRESSES["lido_steth"],
            "symbol": "stETH",
            "protocol": "Lido",
            "apy": 0.04,  # Approximate APY
        },
        "rETH": {
            "address": CONTRACT_ADDRESSES["rocket_pool"],
            "symbol": "rETH",
            "protocol": "Rocket Pool",
            "apy": 0.042,
        },
        "sETH2": {
            "address": CONTRACT_ADDRESSES["stake_wise"],
            "symbol": "sETH2",
            "protocol": "StakeWise",
            "apy": 0.038,
        },
    }

    # Ethereum staking constants
    MIN_VALIDATOR_BALANCE = 32.0  # ETH
    MAX_VALIDATOR_BALANCE = 64.0  # ETH
    VALIDATOR_REWARD_RATE = 0.04  # 4% APY
    SLASHING_PENALTY = 0.12  # 12% penalty

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Ethereum staking integration.

        Args:
            web3_client: Web3 client instance
            config: Configuration dictionary
        """
        super().__init__(
            provider=StakingProvider.ETHEREUM,
            config=config,
        )

        self.web3_client = web3_client
        self._address = self.web3_client.default_account

        # Cache
        self._validators_cache: Dict[str, ETHValidator] = {}
        self._position_cache: Optional[ETHStakingPosition] = None
        self._stats_cache: Optional[ETHStakingStats] = None
        self._liquid_protocols_cache: Dict[str, LiquidStakingProtocol] = {}
        self._last_cache_update: datetime = datetime.utcnow() - timedelta(hours=1)

        # Performance metrics
        self._performance = {
            "validator_queries": 0,
            "position_queries": 0,
            "transactions_sent": 0,
            "rewards_claimed": 0,
            "liquid_stake_operations": 0,
            "avg_response_time_ms": 0.0,
        }

        # Initialize contracts
        self._initialize_contracts()

        logger.info(
            "ETHStaking initialized",
            extra={"address": self._address}
        )

    # -----------------------------------------------------------------------
    # Contract Initialization
    # -----------------------------------------------------------------------

    def _initialize_contracts(self) -> None:
        """Initialize contract interfaces."""
        try:
            # Lido stETH contract
            self._lido_contract = self.web3_client.get_contract(
                self.CONTRACT_ADDRESSES["lido_steth"],
                abi=self._get_lido_abi(),
            )

            # Rocket Pool contract
            self._rocket_pool_contract = self.web3_client.get_contract(
                self.CONTRACT_ADDRESSES["rocket_pool"],
                abi=self._get_rocket_pool_abi(),
            )

            logger.info("Ethereum staking contracts initialized")

        except Exception as e:
            logger.error(f"Error initializing contracts: {e}")
            raise

    # -----------------------------------------------------------------------
    # Validator Management
    # -----------------------------------------------------------------------

    async def get_validators(
        self,
        status: Optional[ETHValidatorStatus] = None,
        limit: Optional[int] = None,
        force_refresh: bool = False,
    ) -> List[ETHValidator]:
        """
        Get Ethereum validators.

        Args:
            status: Filter by status
            limit: Maximum number of validators
            force_refresh: Force refresh cache

        Returns:
            List of ETHValidator
        """
        if not force_refresh and self._validators_cache:
            validators = list(self._validators_cache.values())
            if status:
                validators = [v for v in validators if v.status == status]
            if limit:
                validators = validators[:limit]
            return validators

        try:
            start_time = time.time()

            # Query Beacon Chain API
            validators_data = await self._query_beacon_validators()

            if not validators_data:
                return []

            validators = []
            for v in validators_data:
                validator = self._parse_validator(v)
                self._validators_cache[validator.pubkey] = validator
                validators.append(validator)

            # Update performance
            self._performance["validator_queries"] += 1
            self._performance["avg_response_time_ms"] = (
                (self._performance["avg_response_time_ms"] *
                 (self._performance["validator_queries"] - 1) +
                 (time.time() - start_time) * 1000) /
                self._performance["validator_queries"]
            )

            if status:
                validators = [v for v in validators if v.status == status]

            if limit:
                validators = validators[:limit]

            return validators

        except Exception as e:
            logger.error(f"Error getting validators: {e}")
            return []

    async def _query_beacon_validators(self) -> List[Dict[str, Any]]:
        """Query validators from Beacon Chain API."""
        try:
            # Use public Beacon Chain API
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://beaconcha.in/api/v1/validator",
                    params={"limit": 100},
                    timeout=30,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", [])
                    else:
                        logger.error(f"Error querying validators: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Error querying validators: {e}")
            return []

    def _parse_validator(self, data: Dict[str, Any]) -> ETHValidator:
        """Parse validator data."""
        status_map = {
            "pending": ETHValidatorStatus.PENDING,
            "active": ETHValidatorStatus.ACTIVE,
            "exiting": ETHValidatorStatus.EXITING,
            "slashed": ETHValidatorStatus.SLASHED,
            "withdrawn": ETHValidatorStatus.WITHDRAWN,
        }

        return ETHValidator(
            index=data.get("index", 0),
            pubkey=data.get("pubkey", ""),
            balance=float(data.get("balance", 0)) / 1e9,
            effective_balance=float(data.get("effective_balance", 0)) / 1e9,
            status=status_map.get(data.get("status", "pending"), ETHValidatorStatus.PENDING),
            activation_epoch=data.get("activation_epoch", 0),
            exit_epoch=data.get("exit_epoch", 0),
            withdrawable_epoch=data.get("withdrawable_epoch", 0),
            validator_apy=self.VALIDATOR_REWARD_RATE,
            commission=0.0,
            is_active=data.get("status", "pending") == "active",
            metadata=data.get("metadata", {}),
        )

    async def get_validator(
        self,
        pubkey: str,
        force_refresh: bool = False,
    ) -> Optional[ETHValidator]:
        """
        Get validator by pubkey.

        Args:
            pubkey: Validator pubkey
            force_refresh: Force refresh cache

        Returns:
            ETHValidator or None
        """
        if not force_refresh and pubkey in self._validators_cache:
            return self._validators_cache[pubkey]

        validators = await self.get_validators(force_refresh=True)
        for v in validators:
            if v.pubkey == pubkey:
                return v

        return None

    # -----------------------------------------------------------------------
    # Liquid Staking
    # -----------------------------------------------------------------------

    async def liquid_stake(
        self,
        amount: float,
        protocol: str = "stETH",
        from_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Liquid stake ETH.

        Args:
            amount: Amount to stake
            protocol: Liquid staking protocol
            from_address: From address

        Returns:
            Transaction hash or None
        """
        protocol_info = self.LIQUID_PROTOCOLS.get(protocol)
        if not protocol_info:
            logger.error(f"Unknown liquid staking protocol: {protocol}")
            return None

        from_address = from_address or self._address

        try:
            start_time = time.time()

            amount_wei = self.web3_client.to_wei(amount, "ether")

            # Get protocol contract
            contract = self.web3_client.get_contract(
                protocol_info["address"],
                abi=self._get_liquid_staking_abi(protocol),
            )

            # Build transaction
            tx = await self._build_transaction(
                contract,
                "deposit",
                amount_wei,
                from_address,
            )

            tx_hash = await self.web3_client.send_transaction(tx)

            if tx_hash:
                self._performance["transactions_sent"] += 1
                self._performance["liquid_stake_operations"] += 1
                self._performance["avg_response_time_ms"] = (
                    (self._performance["avg_response_time_ms"] *
                     (self._performance["transactions_sent"] - 1) +
                     (time.time() - start_time) * 1000) /
                    self._performance["transactions_sent"]
                )

                logger.info(
                    f"Liquid staked {amount} ETH via {protocol}",
                    extra={"tx_hash": tx_hash}
                )

                # Clear cache
                self._position_cache = None

            return tx_hash

        except Exception as e:
            logger.error(f"Error liquid staking: {e}")
            return None

    async def liquid_unstake(
        self,
        amount: float,
        protocol: str = "stETH",
        from_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Unstake liquid staked ETH.

        Args:
            amount: Amount to unstake
            protocol: Liquid staking protocol
            from_address: From address

        Returns:
            Transaction hash or None
        """
        protocol_info = self.LIQUID_PROTOCOLS.get(protocol)
        if not protocol_info:
            logger.error(f"Unknown liquid staking protocol: {protocol}")
            return None

        from_address = from_address or self._address

        try:
            amount_wei = self.web3_client.to_wei(amount, "ether")

            contract = self.web3_client.get_contract(
                protocol_info["address"],
                abi=self._get_liquid_staking_abi(protocol),
            )

            tx = await self._build_transaction(
                contract,
                "withdraw",
                amount_wei,
                from_address,
            )

            tx_hash = await self.web3_client.send_transaction(tx)

            if tx_hash:
                logger.info(
                    f"Liquid unstaked {amount} {protocol}",
                    extra={"tx_hash": tx_hash}
                )
                self._position_cache = None

            return tx_hash

        except Exception as e:
            logger.error(f"Error liquid unstaking: {e}")
            return None

    # -----------------------------------------------------------------------
    # Reward Operations
    # -----------------------------------------------------------------------

    async def claim_rewards(
        self,
        validator_indices: Optional[List[int]] = None,
        from_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Claim staking rewards.

        Args:
            validator_indices: List of validator indices
            from_address: From address

        Returns:
            Transaction hash or None
        """
        from_address = from_address or self._address

        try:
            # For Ethereum, rewards are automatically added to validator balance
            # This is a placeholder for withdrawal operations
            logger.info("Ethereum rewards are automatically compounded")
            self._performance["rewards_claimed"] += 1

            return None

        except Exception as e:
            logger.error(f"Error claiming rewards: {e}")
            return None

    # -----------------------------------------------------------------------
    # Staking Position
    # -----------------------------------------------------------------------

    async def get_staking_position(
        self,
        address: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[ETHStakingPosition]:
        """
        Get Ethereum staking position.

        Args:
            address: Staker address
            force_refresh: Force refresh cache

        Returns:
            ETHStakingPosition or None
        """
        address = address or self._address

        if not force_refresh and self._position_cache:
            return self._position_cache

        try:
            start_time = time.time()

            # Get validators
            validators = await self.get_validators()

            # Get liquid staking balances
            liquid_staked = await self._get_liquid_balances(address)

            # Calculate total staked
            total_staked = sum(v.balance for v in validators if v.is_active)
            total_staked += sum(liquid_staked.values())

            # Calculate rewards
            total_rewards = sum(
                v.balance - v.effective_balance
                for v in validators
                if v.is_active and v.balance > v.effective_balance
            )

            # Calculate APY
            apy = await self._calculate_apy()

            # Get ETH price
            price_usd = await self._get_eth_price()

            position = ETHStakingPosition(
                total_staked=total_staked,
                total_rewards=total_rewards,
                total_value_usd=(total_staked + total_rewards) * price_usd,
                validators=validators,
                liquid_staked=liquid_staked,
                staking_type=ETHStakingType.LIQUID if liquid_staked else ETHStakingType.SOLO,
                average_apy=apy,
                daily_rewards=total_rewards / 365,
                weekly_rewards=total_rewards / 365 * 7,
                monthly_rewards=total_rewards / 365 * 30,
                status=StakingStatus.ACTIVE,
            )

            self._position_cache = position
            self._performance["position_queries"] += 1
            self._performance["avg_response_time_ms"] = (
                (self._performance["avg_response_time_ms"] *
                 (self._performance["position_queries"] - 1) +
                 (time.time() - start_time) * 1000) /
                self._performance["position_queries"]
            )

            return position

        except Exception as e:
            logger.error(f"Error getting staking position: {e}")
            return None

    async def _get_liquid_balances(self, address: str) -> Dict[str, float]:
        """Get liquid staking balances."""
        balances = {}

        for protocol, info in self.LIQUID_PROTOCOLS.items():
            try:
                contract = self.web3_client.get_contract(
                    info["address"],
                    abi=self._get_erc20_abi(),
                )

                balance = await self._call_contract_function(
                    contract,
                    "balanceOf",
                    address,
                )

                if balance:
                    balances[protocol] = self.web3_client.from_wei(balance, "ether")

            except Exception as e:
                logger.error(f"Error getting {protocol} balance: {e}")

        return balances

    async def _calculate_apy(self) -> float:
        """Calculate APY."""
        try:
            # Get current ETH staking APY from beacon chain
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://beaconcha.in/api/v1/validator/stats",
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("apy", self.VALIDATOR_REWARD_RATE) * 100

            return self.VALIDATOR_REWARD_RATE * 100

        except Exception as e:
            logger.error(f"Error calculating APY: {e}")
            return self.VALIDATOR_REWARD_RATE * 100

    # -----------------------------------------------------------------------
    # Staking Statistics
    # -----------------------------------------------------------------------

    async def get_staking_stats(self) -> Optional[ETHStakingStats]:
        """
        Get Ethereum staking statistics.

        Returns:
            ETHStakingStats or None
        """
        if self._stats_cache:
            return self._stats_cache

        try:
            # Query beacon chain stats
            beacon_stats = await self._get_beacon_stats()

            # Get liquid staking TVL
            liquid_tvl = await self._get_liquid_tvl()

            # Get ETH price
            price_usd = await self._get_eth_price()

            stats = ETHStakingStats(
                total_eth_staked=beacon_stats.get("total_staked", 0),
                total_validators=beacon_stats.get("total_validators", 0),
                active_validators=beacon_stats.get("active_validators", 0),
                average_apy=self.VALIDATOR_REWARD_RATE * 100,
                min_apy=0.03 * 100,
                max_apy=0.05 * 100,
                median_apy=0.04 * 100,
                staking_rate=beacon_stats.get("staking_rate", 0),
                total_staked_usd=beacon_stats.get("total_staked", 0) * price_usd,
                liquid_staking_tvl=liquid_tvl,
                beacon_chain_validators=beacon_stats.get("total_validators", 0),
                avg_validator_balance=beacon_stats.get("avg_balance", 32.0),
                last_updated=datetime.utcnow(),
            )

            self._stats_cache = stats
            return stats

        except Exception as e:
            logger.error(f"Error getting staking stats: {e}")
            return None

    async def _get_beacon_stats(self) -> Dict[str, Any]:
        """Get beacon chain statistics."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://beaconcha.in/api/v1/eth1/statistics",
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", {})
                    return {}

        except Exception as e:
            logger.error(f"Error getting beacon stats: {e}")
            return {}

    async def _get_liquid_tvl(self) -> float:
        """Get liquid staking TVL."""
        try:
            total_tvl = 0
            for protocol in self.LIQUID_PROTOCOLS.values():
                tvl = await self._get_protocol_tvl(protocol["address"])
                total_tvl += tvl
            return total_tvl

        except Exception as e:
            logger.error(f"Error getting liquid TVL: {e}")
            return 0.0

    async def _get_protocol_tvl(self, address: str) -> float:
        """Get protocol TVL."""
        try:
            # Would query protocol contract for TVL
            return 0.0

        except Exception:
            return 0.0

    # -----------------------------------------------------------------------
    # Price Queries
    # -----------------------------------------------------------------------

    async def _get_eth_price(self) -> float:
        """Get ETH price in USD."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": "ethereum", "vs_currencies": "usd"},
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("ethereum", {}).get("usd", 0.0)
                    return 0.0

        except Exception as e:
            logger.error(f"Error getting ETH price: {e}")
            return 0.0

    # -----------------------------------------------------------------------
    # Contract ABIs
    # -----------------------------------------------------------------------

    def _get_lido_abi(self) -> List[Dict[str, Any]]:
        """Get Lido stETH ABI."""
        return [
            {
                "constant": False,
                "inputs": [{"name": "_referral", "type": "address"}],
                "name": "submit",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
        ]

    def _get_rocket_pool_abi(self) -> List[Dict[str, Any]]:
        """Get Rocket Pool ABI."""
        return [
            {
                "constant": False,
                "inputs": [],
                "name": "deposit",
                "outputs": [],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_address", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
        ]

    def _get_liquid_staking_abi(self, protocol: str) -> List[Dict[str, Any]]:
        """Get liquid staking protocol ABI."""
        if protocol == "stETH":
            return self._get_lido_abi()
        elif protocol == "rETH":
            return self._get_rocket_pool_abi()
        else:
            return self._get_erc20_abi()

    def _get_erc20_abi(self) -> List[Dict[str, Any]]:
        """Get ERC20 ABI."""
        return [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
        ]

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    async def _call_contract_function(
        self,
        contract,
        function_name: str,
        *args,
    ) -> Any:
        """Call a contract function."""
        try:
            func = getattr(contract.functions, function_name)
            return await asyncio.to_thread(func(*args).call)
        except Exception as e:
            logger.error(f"Error calling {function_name}: {e}")
            return None

    async def _build_transaction(
        self,
        contract,
        function_name: str,
        *args,
    ) -> Dict[str, Any]:
        """Build a transaction."""
        try:
            func = getattr(contract.functions, function_name)
            tx = func(*args).build_transaction({
                "from": self.web3_client.default_account,
                "nonce": await self.web3_client.get_nonce(self.web3_client.default_account),
                "gas": 0,
                "gasPrice": await self.web3_client.get_gas_price(),
            })

            gas = await self.web3_client.estimate_gas(tx)
            tx["gas"] = int(gas * 1.3)

            return tx

        except Exception as e:
            logger.error(f"Error building transaction: {e}")
            raise

    # -----------------------------------------------------------------------
    # Health Check
    # -----------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            block_number = await self.web3_client.get_block_number()
            chain_healthy = block_number is not None

            # Check Beacon Chain API
            beacon_healthy = False
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://beaconcha.in/api/v1/eth1/statistics",
                        timeout=10,
                    ) as response:
                        beacon_healthy = response.status == 200
            except:
                pass

            return {
                "status": "healthy" if chain_healthy and beacon_healthy else "unhealthy",
                "chain_healthy": chain_healthy,
                "beacon_healthy": beacon_healthy,
                "address": self._address,
                "block_number": block_number,
                "cached_validators": len(self._validators_cache),
                "position_cached": self._position_cache is not None,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    # -----------------------------------------------------------------------
    # Performance Metrics
    # -----------------------------------------------------------------------

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "cached_validators": len(self._validators_cache),
            "position_cached": self._position_cache is not None,
            "address": self._address,
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the staking integration."""
        if self._running:
            return

        self._running = True
        logger.info("ETHStaking started")

    async def stop(self) -> None:
        """Stop the staking integration."""
        self._running = False

        # Clear caches
        self._validators_cache.clear()
        self._position_cache = None
        self._stats_cache = None

        logger.info("ETHStaking stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_eth_staking(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> ETHStaking:
    """
    Factory function to create an ETHStaking instance.

    Args:
        web3_client: Web3 client instance
        config: Configuration dictionary

    Returns:
        ETHStaking instance
    """
    return ETHStaking(
        web3_client=web3_client,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use ETH staking
    pass
