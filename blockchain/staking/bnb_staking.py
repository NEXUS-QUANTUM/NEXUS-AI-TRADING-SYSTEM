# blockchain/staking/bnb_staking.py
# NEXUS AI TRADING SYSTEM - BNB Staking Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
BNB Staking Integration for NEXUS AI Trading System.
Provides comprehensive staking operations for BNB including:
- BNB Chain staking (validator delegation)
- BNB Beacon Chain staking
- Liquid staking (stBNB, BNBx)
- Auto-compounding
- Validator management
- Reward claiming
- APR/APY calculations
- Risk assessment
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

logger = get_logger("nexus.blockchain.staking.bnb")


# ============================================================================
# Enums & Constants
# ============================================================================

class BNBStakingType(str, Enum):
    """BNB staking types."""
    BNB_CHAIN = "bnb_chain"  # BNB Chain validator staking
    BEACON_CHAIN = "beacon_chain"  # BNB Beacon Chain staking
    LIQUID = "liquid"  # Liquid staking (stBNB, BNBx)
    AUTO_COMPOUND = "auto_compound"  # Auto-compounding staking


class BNBStakingAction(str, Enum):
    """BNB staking actions."""
    DELEGATE = "delegate"
    UNDELEGATE = "undelegate"
    REDELEGATE = "redelegate"
    CLAIM_REWARDS = "claim_rewards"
    COMPOUND = "compound"
    LIQUID_STAKE = "liquid_stake"
    LIQUID_UNSTAKE = "liquid_unstake"
    RESTAKE = "restake"


@dataclass
class BNBValidator:
    """BNB validator information."""
    address: str
    name: str
    commission_rate: float
    max_commission_rate: float
    voting_power: float
    delegators: int
    self_delegation: float
    apy: float
    status: ValidatorStatus
    score: float
    is_jailed: bool
    uptime: float
    rank: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BNBStakingPosition:
    """BNB staking position."""
    total_staked: float
    total_rewards: float
    total_value_usd: float
    delegations: List[Dict[str, Any]]
    validators: List[BNBValidator]
    liquid_staked: float
    liquid_staked_asset: str
    unbonding_amount: float
    unbonding_time: Optional[datetime] = None
    average_apy: float = 0.0
    daily_rewards: float = 0.0
    weekly_rewards: float = 0.0
    monthly_rewards: float = 0.0
    status: StakingStatus = StakingStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BNBStakingStats:
    """BNB staking statistics."""
    total_bnb_staked: float
    total_validators: int
    active_validators: int
    average_apy: float
    min_apy: float
    max_apy: float
    median_apy: float
    total_staked_usd: float
    inflation_rate: float
    community_pool: float
    bonded_tokens: float
    unbonding_tokens: float
    liquid_staking_tvl: float
    last_updated: datetime


# ============================================================================
# BNB Staking Integration
# ============================================================================

class BNBStaking(BaseStaking):
    """
    BNB Staking Integration.
    Provides comprehensive staking operations for BNB.
    """

    # BNB Chain contract addresses
    CONTRACT_ADDRESSES = {
        "validator_set": "0x0000000000000000000000000000000000001000",
        "staking": "0x0000000000000000000000000000000000002000",
        "slashing": "0x0000000000000000000000000000000000003000",
        "reward": "0x0000000000000000000000000000000000004000",
        "gov": "0x0000000000000000000000000000000000005000",
    }

    # Liquid staking protocols
    LIQUID_STAKING_PROTOCOLS = {
        "stBNB": {
            "address": "0xB0b84D294e0C75A6abe60171b70edEb2EFd14A1B",
            "symbol": "stBNB",
            "protocol": "Stader",
        },
        "BNBx": {
            "address": "0x1bdd3Cf7F79cfB8EdbB955f20ad99211551BA275",
            "symbol": "BNBx",
            "protocol": "PancakeSwap",
        },
        "ankrBNB": {
            "address": "0x52F24a5eC2eAc75B5E1C9dB295545a3972515892",
            "symbol": "ankrBNB",
            "protocol": "Ankr",
        },
    }

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize BNB staking integration.

        Args:
            web3_client: Web3 client instance
            config: Configuration dictionary
        """
        super().__init__(
            provider=StakingProvider.BNB,
            config=config,
        )

        self.web3_client = web3_client
        self._address = self.web3_client.default_account

        # Cache
        self._validators_cache: Dict[str, BNBValidator] = {}
        self._position_cache: Optional[BNBStakingPosition] = None
        self._stats_cache: Optional[BNBStakingStats] = None
        self._last_cache_update: datetime = datetime.utcnow() - timedelta(hours=1)

        # Performance metrics
        self._performance = {
            "validator_queries": 0,
            "position_queries": 0,
            "transactions_sent": 0,
            "rewards_claimed": 0,
            "compounds": 0,
            "avg_response_time_ms": 0.0,
        }

        logger.info(
            "BNBStaking initialized",
            extra={"address": self._address}
        )

    # -----------------------------------------------------------------------
    # Validator Management
    # -----------------------------------------------------------------------

    async def get_validators(
        self,
        status: Optional[ValidatorStatus] = None,
        limit: Optional[int] = None,
        force_refresh: bool = False,
    ) -> List[BNBValidator]:
        """
        Get BNB validators.

        Args:
            status: Filter by status
            limit: Maximum number of validators
            force_refresh: Force refresh cache

        Returns:
            List of BNBValidator
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

            # Fetch validators from BNB Chain
            validators_data = await self._fetch_validators()

            if not validators_data:
                return []

            validators = []
            for v in validators_data:
                validator = self._parse_validator(v)
                self._validators_cache[validator.address] = validator
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

    async def _fetch_validators(self) -> List[Dict[str, Any]]:
        """Fetch validators from BNB Chain."""
        try:
            # Use BNB Chain validator set contract
            validator_set = self.web3_client.get_contract(
                self.CONTRACT_ADDRESSES["validator_set"],
            )

            # Get validator count
            count = await self._call_contract_function(
                validator_set,
                "validatorCount",
            )

            if not count:
                return []

            validators = []
            for i in range(min(int(count), 100)):
                validator = await self._call_contract_function(
                    validator_set,
                    "validators",
                    i,
                )
                if validator:
                    validators.append(self._parse_validator_data(validator))

            return validators

        except Exception as e:
            logger.error(f"Error fetching validators: {e}")
            return []

    def _parse_validator(self, data: Dict[str, Any]) -> BNBValidator:
        """Parse validator data."""
        status = data.get("status", "active")
        status_map = {
            "active": ValidatorStatus.ACTIVE,
            "inactive": ValidatorStatus.INACTIVE,
            "jailed": ValidatorStatus.JAILED,
            "unbonding": ValidatorStatus.UNBONDING,
            "tombstoned": ValidatorStatus.TOMBSTONED,
        }

        return BNBValidator(
            address=data.get("address", ""),
            name=data.get("name", "Unknown"),
            commission_rate=float(data.get("commission_rate", 0)),
            max_commission_rate=float(data.get("max_commission_rate", 0)),
            voting_power=float(data.get("voting_power", 0)),
            delegators=int(data.get("delegators", 0)),
            self_delegation=float(data.get("self_delegation", 0)),
            apy=float(data.get("apy", 0)),
            status=status_map.get(status, ValidatorStatus.INACTIVE),
            score=float(data.get("score", 0)),
            is_jailed=data.get("jailed", False),
            uptime=float(data.get("uptime", 100)),
            rank=int(data.get("rank", 0)),
            metadata=data.get("metadata", {}),
        )

    def _parse_validator_data(self, data: Any) -> Dict[str, Any]:
        """Parse raw validator data from contract."""
        # Parse contract data structure
        return {
            "address": data.get("address", ""),
            "name": data.get("name", ""),
            "commission_rate": data.get("commission_rate", 0),
            "max_commission_rate": data.get("max_commission_rate", 0),
            "voting_power": data.get("voting_power", 0),
            "delegators": data.get("delegators", 0),
            "self_delegation": data.get("self_delegation", 0),
            "status": data.get("status", "inactive"),
            "jailed": data.get("jailed", False),
        }

    async def get_validator(
        self,
        validator_address: str,
        force_refresh: bool = False,
    ) -> Optional[BNBValidator]:
        """
        Get validator by address.

        Args:
            validator_address: Validator address
            force_refresh: Force refresh cache

        Returns:
            BNBValidator or None
        """
        if not force_refresh and validator_address in self._validators_cache:
            return self._validators_cache[validator_address]

        validators = await self.get_validators(force_refresh=True)
        for v in validators:
            if v.address.lower() == validator_address.lower():
                return v

        return None

    async def get_top_validators(
        self,
        limit: int = 10,
    ) -> List[BNBValidator]:
        """
        Get top validators by voting power.

        Args:
            limit: Number of validators

        Returns:
            List of BNBValidator
        """
        validators = await self.get_validators(status=ValidatorStatus.ACTIVE)
        validators.sort(key=lambda v: v.voting_power, reverse=True)

        for i, v in enumerate(validators[:limit]):
            v.rank = i + 1

        return validators[:limit]

    # -----------------------------------------------------------------------
    # Staking Operations
    # -----------------------------------------------------------------------

    async def delegate(
        self,
        validator_address: str,
        amount: float,
        memo: Optional[str] = None,
    ) -> Optional[str]:
        """
        Delegate BNB to a validator.

        Args:
            validator_address: Validator address
            amount: Amount to delegate
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        try:
            start_time = time.time()

            # Build delegation transaction
            amount_wei = self.web3_client.to_wei(amount, "ether")

            staking_contract = self.web3_client.get_contract(
                self.CONTRACT_ADDRESSES["staking"],
            )

            tx = await self._build_transaction(
                staking_contract,
                "delegate",
                validator_address,
                amount_wei,
            )

            tx_hash = await self.web3_client.send_transaction(tx)

            if tx_hash:
                self._performance["transactions_sent"] += 1
                self._performance["avg_response_time_ms"] = (
                    (self._performance["avg_response_time_ms"] *
                     (self._performance["transactions_sent"] - 1) +
                     (time.time() - start_time) * 1000) /
                    self._performance["transactions_sent"]
                )

                logger.info(
                    f"Delegated {amount} BNB to {validator_address}",
                    extra={"tx_hash": tx_hash}
                )

                # Clear cache
                self._position_cache = None

            return tx_hash

        except Exception as e:
            logger.error(f"Error delegating: {e}")
            return None

    async def undelegate(
        self,
        validator_address: str,
        amount: float,
        memo: Optional[str] = None,
    ) -> Optional[str]:
        """
        Undelegate BNB from a validator.

        Args:
            validator_address: Validator address
            amount: Amount to undelegate
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        try:
            amount_wei = self.web3_client.to_wei(amount, "ether")

            staking_contract = self.web3_client.get_contract(
                self.CONTRACT_ADDRESSES["staking"],
            )

            tx = await self._build_transaction(
                staking_contract,
                "undelegate",
                validator_address,
                amount_wei,
            )

            tx_hash = await self.web3_client.send_transaction(tx)

            if tx_hash:
                logger.info(
                    f"Undelegated {amount} BNB from {validator_address}",
                    extra={"tx_hash": tx_hash}
                )
                self._position_cache = None

            return tx_hash

        except Exception as e:
            logger.error(f"Error undelegating: {e}")
            return None

    async def claim_rewards(
        self,
        validator_addresses: Optional[List[str]] = None,
        memo: Optional[str] = None,
    ) -> Optional[str]:
        """
        Claim staking rewards.

        Args:
            validator_addresses: List of validator addresses
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        try:
            reward_contract = self.web3_client.get_contract(
                self.CONTRACT_ADDRESSES["reward"],
            )

            if validator_addresses:
                # Claim from specific validators
                tx = await self._build_transaction(
                    reward_contract,
                    "claimRewards",
                    validator_addresses,
                )
            else:
                # Claim from all validators
                position = await self.get_staking_position()
                if not position:
                    return None

                validator_addrs = [d["validator_address"] for d in position.delegations]
                if not validator_addrs:
                    logger.warning("No validators to claim from")
                    return None

                tx = await self._build_transaction(
                    reward_contract,
                    "claimRewards",
                    validator_addrs,
                )

            tx_hash = await self.web3_client.send_transaction(tx)

            if tx_hash:
                self._performance["rewards_claimed"] += 1
                logger.info(
                    f"Claimed rewards from {len(validator_addresses or [])} validators",
                    extra={"tx_hash": tx_hash}
                )
                self._position_cache = None

            return tx_hash

        except Exception as e:
            logger.error(f"Error claiming rewards: {e}")
            return None

    # -----------------------------------------------------------------------
    # Liquid Staking
    # -----------------------------------------------------------------------

    async def liquid_stake(
        self,
        amount: float,
        protocol: str = "stBNB",
    ) -> Optional[str]:
        """
        Liquid stake BNB.

        Args:
            amount: Amount to stake
            protocol: Liquid staking protocol

        Returns:
            Transaction hash or None
        """
        try:
            protocol_info = self.LIQUID_STAKING_PROTOCOLS.get(protocol)
            if not protocol_info:
                logger.error(f"Unknown liquid staking protocol: {protocol}")
                return None

            amount_wei = self.web3_client.to_wei(amount, "ether")

            # Get protocol contract
            protocol_contract = self.web3_client.get_contract(
                protocol_info["address"],
            )

            # Different protocols may have different interfaces
            tx = await self._build_transaction(
                protocol_contract,
                "deposit",
                amount_wei,
            )

            tx_hash = await self.web3_client.send_transaction(tx)

            if tx_hash:
                self._performance["transactions_sent"] += 1
                logger.info(
                    f"Liquid staked {amount} BNB via {protocol}",
                    extra={"tx_hash": tx_hash}
                )
                self._position_cache = None

            return tx_hash

        except Exception as e:
            logger.error(f"Error liquid staking: {e}")
            return None

    async def liquid_unstake(
        self,
        amount: float,
        protocol: str = "stBNB",
    ) -> Optional[str]:
        """
        Unstake liquid staked BNB.

        Args:
            amount: Amount to unstake
            protocol: Liquid staking protocol

        Returns:
            Transaction hash or None
        """
        try:
            protocol_info = self.LIQUID_STAKING_PROTOCOLS.get(protocol)
            if not protocol_info:
                logger.error(f"Unknown liquid staking protocol: {protocol}")
                return None

            amount_wei = self.web3_client.to_wei(amount, "ether")

            protocol_contract = self.web3_client.get_contract(
                protocol_info["address"],
            )

            tx = await self._build_transaction(
                protocol_contract,
                "withdraw",
                amount_wei,
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
    # Auto-Compounding
    # -----------------------------------------------------------------------

    async def compound_rewards(
        self,
        validator_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Compound rewards by claiming and restaking.

        Args:
            validator_address: Validator to restake to (optional)

        Returns:
            Transaction hash or None
        """
        try:
            position = await self.get_staking_position()
            if not position:
                return None

            # Claim rewards
            claim_hash = await self.claim_rewards()
            if not claim_hash:
                return None

            # Wait for transaction
            await asyncio.sleep(2)

            # Get updated position
            position = await self.get_staking_position(force_refresh=True)

            # Delegate rewards
            if position.total_rewards > 0:
                validator = validator_address or position.validators[0].address if position.validators else None
                if validator:
                    delegate_hash = await self.delegate(validator, position.total_rewards)
                    if delegate_hash:
                        self._performance["compounds"] += 1
                        return delegate_hash

            return None

        except Exception as e:
            logger.error(f"Error compounding: {e}")
            return None

    # -----------------------------------------------------------------------
    # Position Queries
    # -----------------------------------------------------------------------

    async def get_staking_position(
        self,
        address: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[BNBStakingPosition]:
        """
        Get BNB staking position.

        Args:
            address: Staker address
            force_refresh: Force refresh cache

        Returns:
            BNBStakingPosition or None
        """
        address = address or self._address

        if not force_refresh and self._position_cache:
            return self._position_cache

        try:
            start_time = time.time()

            # Get delegations
            delegations = await self._get_delegations(address)

            # Get validators
            validators = []
            total_staked = 0
            total_rewards = 0

            for d in delegations:
                validator = await self.get_validator(d.get("validator_address", ""))
                if validator:
                    validators.append(validator)
                total_staked += d.get("amount", 0)
                total_rewards += d.get("rewards", 0)

            # Get liquid staking positions
            liquid_staked = await self._get_liquid_staked(address)

            # Get unbonding
            unbonding = await self._get_unbonding(address)

            # Calculate APY
            avg_apy = sum(v.apy for v in validators) / len(validators) if validators else 0

            # Get BNB price
            price_usd = await self._get_bnb_price()

            position = BNBStakingPosition(
                total_staked=total_staked,
                total_rewards=total_rewards,
                total_value_usd=(total_staked + total_rewards) * price_usd,
                delegations=delegations,
                validators=validators,
                liquid_staked=liquid_staked.get("amount", 0),
                liquid_staked_asset=liquid_staked.get("asset", ""),
                unbonding_amount=unbonding.get("amount", 0),
                unbonding_time=unbonding.get("completion_time"),
                average_apy=avg_apy,
                daily_rewards=total_rewards / 30,
                weekly_rewards=total_rewards / 30 * 7,
                monthly_rewards=total_rewards,
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

    async def _get_delegations(self, address: str) -> List[Dict[str, Any]]:
        """Get delegations for an address."""
        try:
            staking_contract = self.web3_client.get_contract(
                self.CONTRACT_ADDRESSES["staking"],
            )

            delegations = await self._call_contract_function(
                staking_contract,
                "getDelegations",
                address,
            )

            return delegations if delegations else []

        except Exception as e:
            logger.error(f"Error getting delegations: {e}")
            return []

    async def _get_liquid_staked(self, address: str) -> Dict[str, Any]:
        """Get liquid staked positions."""
        try:
            total_liquid = 0
            for protocol, info in self.LIQUID_STAKING_PROTOCOLS.items():
                contract = self.web3_client.get_contract(info["address"])
                balance = await self._call_contract_function(
                    contract,
                    "balanceOf",
                    address,
                )
                if balance:
                    total_liquid += self.web3_client.from_wei(balance, "ether")

            return {
                "amount": total_liquid,
                "asset": "BNB",
            }

        except Exception as e:
            logger.error(f"Error getting liquid staked: {e}")
            return {"amount": 0, "asset": ""}

    async def _get_unbonding(self, address: str) -> Dict[str, Any]:
        """Get unbonding information."""
        try:
            staking_contract = self.web3_client.get_contract(
                self.CONTRACT_ADDRESSES["staking"],
            )

            unbonding = await self._call_contract_function(
                staking_contract,
                "getUnbondingDelegations",
                address,
            )

            return {
                "amount": unbonding.get("amount", 0),
                "completion_time": unbonding.get("completion_time"),
            }

        except Exception as e:
            logger.error(f"Error getting unbonding: {e}")
            return {"amount": 0}

    # -----------------------------------------------------------------------
    # Statistics
    # -----------------------------------------------------------------------

    async def get_staking_stats(self) -> Optional[BNBStakingStats]:
        """
        Get BNB staking statistics.

        Returns:
            BNBStakingStats or None
        """
        if self._stats_cache:
            return self._stats_cache

        try:
            validators = await self.get_validators()

            active_validators = [v for v in validators if v.status == ValidatorStatus.ACTIVE]
            apys = [v.apy for v in active_validators if v.apy > 0]

            # Get staking pool info
            pool_info = await self._get_staking_pool()

            # Get BNB price
            price_usd = await self._get_bnb_price()

            stats = BNBStakingStats(
                total_bnb_staked=pool_info.get("bonded_tokens", 0),
                total_validators=len(validators),
                active_validators=len(active_validators),
                average_apy=sum(apys) / len(apys) if apys else 0,
                min_apy=min(apys) if apys else 0,
                max_apy=max(apys) if apys else 0,
                median_apy=sorted(apys)[len(apys) // 2] if apys else 0,
                total_staked_usd=pool_info.get("bonded_tokens", 0) * price_usd,
                inflation_rate=pool_info.get("inflation_rate", 0),
                community_pool=pool_info.get("community_pool", 0),
                bonded_tokens=pool_info.get("bonded_tokens", 0),
                unbonding_tokens=pool_info.get("unbonding_tokens", 0),
                liquid_staking_tvl=pool_info.get("liquid_staking_tvl", 0),
                last_updated=datetime.utcnow(),
            )

            self._stats_cache = stats
            return stats

        except Exception as e:
            logger.error(f"Error getting staking stats: {e}")
            return None

    async def _get_staking_pool(self) -> Dict[str, Any]:
        """Get staking pool information."""
        try:
            staking_contract = self.web3_client.get_contract(
                self.CONTRACT_ADDRESSES["staking"],
            )

            pool = await self._call_contract_function(
                staking_contract,
                "getPoolInfo",
            )

            return pool if pool else {}

        except Exception as e:
            logger.error(f"Error getting staking pool: {e}")
            return {}

    # -----------------------------------------------------------------------
    # Price Queries
    # -----------------------------------------------------------------------

    async def _get_bnb_price(self) -> float:
        """Get BNB price in USD."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": "binancecoin", "vs_currencies": "usd"},
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("binancecoin", {}).get("usd", 0.0)
                    return 0.0

        except Exception as e:
            logger.error(f"Error getting BNB price: {e}")
            return 0.0

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

            # Estimate gas
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
            # Check connection to BNB Chain
            block_number = await self.web3_client.get_block_number()
            chain_healthy = block_number is not None

            # Check validator data
            validators = await self.get_validators(limit=1)
            validators_available = bool(validators)

            return {
                "status": "healthy" if chain_healthy and validators_available else "unhealthy",
                "chain_healthy": chain_healthy,
                "validators_available": validators_available,
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
        logger.info("BNBStaking started")

    async def stop(self) -> None:
        """Stop the staking integration."""
        self._running = False

        # Clear caches
        self._validators_cache.clear()
        self._position_cache = None
        self._stats_cache = None

        logger.info("BNBStaking stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_bnb_staking(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> BNBStaking:
    """
    Factory function to create a BNBStaking instance.

    Args:
        web3_client: Web3 client instance
        config: Configuration dictionary

    Returns:
        BNBStaking instance
    """
    return BNBStaking(
        web3_client=web3_client,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use BNB staking
    pass
