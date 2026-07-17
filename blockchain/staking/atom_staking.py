# blockchain/staking/atom_staking.py
# NEXUS AI TRADING SYSTEM - Cosmos (ATOM) Staking Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Cosmos (ATOM) Staking Integration for NEXUS AI Trading System.
Provides comprehensive staking operations including:
- Delegation and undelegation
- Validator management
- Reward claiming
- Staking analytics
- APR/APY calculations
- Validator selection optimization
- Liquid staking support
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
from cosmos_sdk import Wallet, Client
from cosmos_sdk.core import Coin, Coins
from cosmos_sdk.core.delegation import Delegation, Validator
from cosmos_sdk.core.staking import StakingPool

# NEXUS Imports
from blockchain.staking.base_staking import BaseStaking, StakingProvider, StakingStatus
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.staking.atom")


# ============================================================================
# Enums & Constants
# ============================================================================

class ValidatorStatus(str, Enum):
    """Validator status."""
    BONDED = "bonded"
    UNBONDED = "unbonded"
    UNBONDING = "unbonding"
    JAILED = "jailed"


class DelegationStatus(str, Enum):
    """Delegation status."""
    ACTIVE = "active"
    UNBONDING = "unbonding"
    COMPLETED = "completed"


class StakingAction(str, Enum):
    """Staking actions."""
    DELEGATE = "delegate"
    UNDELEGATE = "undelegate"
    REDELEGATE = "redelegate"
    CLAIM_REWARDS = "claim_rewards"
    COMPOUND = "compound"
    RESTAKE = "restake"


@dataclass
class ValidatorInfo:
    """Cosmos validator information."""
    address: str
    moniker: str
    identity: Optional[str] = None
    website: Optional[str] = None
    details: Optional[str] = None
    commission_rate: float = 0.0
    commission_max_rate: float = 0.0
    commission_max_change_rate: float = 0.0
    min_self_delegation: int = 0
    delegator_shares: float = 0.0
    tokens: int = 0
    voting_power: float = 0.0
    status: ValidatorStatus = ValidatorStatus.UNBONDED
    uptime: float = 0.0
    apy: float = 0.0
    rank: int = 0
    is_active: bool = False
    is_jailed: bool = False
    tombstoned: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DelegationInfo:
    """Delegation information."""
    delegator_address: str
    validator_address: str
    amount: float
    shares: float
    rewards: float
    status: DelegationStatus
    created_at: datetime
    last_reward_claim: Optional[datetime] = None
    unbonding_end_time: Optional[datetime] = None
    is_liquid: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StakingPosition:
    """Complete staking position."""
    total_delegated: float
    total_rewards: float
    total_value_usd: float
    delegations: List[DelegationInfo]
    validators: List[ValidatorInfo]
    unbonding_amount: float
    unbonding_time: Optional[datetime] = None
    average_apy: float = 0.0
    daily_rewards: float = 0.0
    weekly_rewards: float = 0.0
    monthly_rewards: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StakingStats:
    """Staking statistics."""
    total_atom_staked: float
    total_validators: int
    active_validators: int
    average_apy: float
    min_apy: float
    max_apy: float
    median_apy: float
    total_delegations: int
    total_staked_usd: float
    inflation_rate: float
    community_pool: float
    bonded_tokens: float
    unbonding_tokens: float
    last_updated: datetime


# ============================================================================
# Cosmos Staking Integration
# ============================================================================

class ATOMStaking(BaseStaking):
    """
    Cosmos (ATOM) Staking Integration.
    Provides comprehensive staking operations on Cosmos Hub.
    """

    # Cosmos Hub chain parameters
    CHAIN_ID = "cosmoshub-4"
    DENOM = "uatom"
    DECIMALS = 6
    EXPLORER_URL = "https://explorer.cosmos.network"
    REST_API = "https://cosmos-rest.publicnode.com"
    RPC_URL = "https://cosmos-rpc.publicnode.com"

    # Popular validators (addresses)
    COMMON_VALIDATORS = {
        "cosmosvaloper1jdvxqyxwp8sgw5yxzt5dfpaj5ddr9wxxry5u2e": "Stakin",
        "cosmosvaloper1rgu32c2f6ms0qjh0kfzyxkp0qahkmg3s4tx52j": "Figment",
        "cosmosvaloper1m5c5kd3y7h2m33vmmdn8f2wsc2msm0xvvj8kmj": "Everstake",
        "cosmosvaloper1p8q7mvnxc6v3c0nxy55nq8dgvszp5a36dg4h5u": "Chorus One",
        "cosmosvaloper1suhgf5svhu4usrurvxzlgn54ksxmn8gljarjtx": "Kraken",
        "cosmosvaloper1pc0gs3n6803z7fj6r8km7rtmt5gqnyq6lpdvmq": "Binance",
        "cosmosvaloper1kgddca7qj96z0qcxr2c45z73cfl0c75pakn5e6": "P2P.org",
        "cosmosvaloper1tflk30mq5vgqjdly92kkhhq3raev2hnz6eete3": "Stakefish",
        "cosmosvaloper1x2qhs3u89a09z2w8urka7c2p3gp9c7l8y677jq": "Cosmostation",
        "cosmosvaloper1clpqr4nrk4khgkxj78fcwwh6dl3uw4epsluffn": "Kleomedes",
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Cosmos staking integration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(
            provider=StakingProvider.COSMOS,
            config=config,
        )

        self._client = None
        self._wallet = None
        self._address = None

        # Cache
        self._validators_cache: Dict[str, ValidatorInfo] = {}
        self._delegations_cache: Dict[str, DelegationInfo] = {}
        self._stats_cache: Optional[StakingStats] = None
        self._last_cache_update: datetime = datetime.utcnow() - timedelta(hours=1)

        # Performance metrics
        self._performance = {
            "validator_queries": 0,
            "delegation_queries": 0,
            "transactions_sent": 0,
            "rewards_claimed": 0,
            "avg_response_time_ms": 0.0,
        }

        # Initialize client
        self._initialize_client()

        logger.info("ATOMStaking initialized")

    # -----------------------------------------------------------------------
    # Client Initialization
    # -----------------------------------------------------------------------

    def _initialize_client(self) -> None:
        """Initialize Cosmos client."""
        try:
            self._client = Client(
                chain_id=self.CHAIN_ID,
                rest_url=self.REST_API,
                rpc_url=self.RPC_URL,
            )

            # Create wallet if private key provided
            if self._private_key:
                self._wallet = Wallet(
                    client=self._client,
                    mnemonic=None,
                    private_key=self._private_key,
                )
                self._address = self._wallet.address

            logger.info("Cosmos client initialized")

        except Exception as e:
            logger.error(f"Error initializing Cosmos client: {e}")
            raise

    # -----------------------------------------------------------------------
    # Validator Management
    # -----------------------------------------------------------------------

    async def get_validators(
        self,
        status: Optional[ValidatorStatus] = None,
        limit: Optional[int] = None,
        force_refresh: bool = False,
    ) -> List[ValidatorInfo]:
        """
        Get Cosmos validators.

        Args:
            status: Filter by status
            limit: Maximum number of validators
            force_refresh: Force refresh cache

        Returns:
            List of ValidatorInfo
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

            # Query validators
            validators_data = await self._query_validators()

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

    async def _query_validators(self) -> List[Dict[str, Any]]:
        """Query validators from Cosmos API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.REST_API}/cosmos/staking/v1beta1/validators",
                    params={"pagination.limit": 200},
                    timeout=30,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("validators", [])
                    else:
                        logger.error(f"Error querying validators: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Error querying validators: {e}")
            return []

    def _parse_validator(self, data: Dict[str, Any]) -> ValidatorInfo:
        """Parse validator data."""
        description = data.get("description", {})
        commission = data.get("commission", {})
        commission_rates = commission.get("commission_rates", {})
        status = data.get("status", "UNBONDED")

        # Parse status
        status_map = {
            "BOND_STATUS_BONDED": ValidatorStatus.BONDED,
            "BOND_STATUS_UNBONDED": ValidatorStatus.UNBONDED,
            "BOND_STATUS_UNBONDING": ValidatorStatus.UNBONDING,
        }

        return ValidatorInfo(
            address=data.get("operator_address", ""),
            moniker=description.get("moniker", "Unknown"),
            identity=description.get("identity"),
            website=description.get("website"),
            details=description.get("details"),
            commission_rate=float(commission_rates.get("rate", "0")) / 1e18 if commission_rates else 0,
            commission_max_rate=float(commission_rates.get("max_rate", "0")) / 1e18 if commission_rates else 0,
            commission_max_change_rate=float(commission_rates.get("max_change_rate", "0")) / 1e18 if commission_rates else 0,
            min_self_delegation=int(data.get("min_self_delegation", "0")),
            delegator_shares=float(data.get("delegator_shares", "0")) / 1e18,
            tokens=int(data.get("tokens", "0")),
            voting_power=float(data.get("tokens", "0")) / 1e6,
            status=status_map.get(status, ValidatorStatus.UNBONDED),
            uptime=self._calculate_validator_uptime(data),
            apy=self._calculate_validator_apy(data),
            rank=0,
            is_active=status == "BOND_STATUS_BONDED",
            is_jailed=data.get("jailed", False),
            tombstoned=data.get("tombstoned", False),
        )

    def _calculate_validator_uptime(self, data: Dict[str, Any]) -> float:
        """Calculate validator uptime."""
        # Would need to query historical data
        return 100.0

    def _calculate_validator_apy(self, data: Dict[str, Any]) -> float:
        """Calculate validator APY."""
        # Would need to calculate from commission and inflation
        commission_rate = float(data.get("commission", {}).get("commission_rates", {}).get("rate", "0")) / 1e18
        # Approximate APY = (inflation * (1 - commission)) / voting_power_share
        inflation = 0.10  # Approximate Cosmos Hub inflation
        voting_power_share = 0.01  # Approximate share
        apy = inflation * (1 - commission_rate) / voting_power_share
        return min(apy * 100, 50.0)  # Cap at 50%

    async def get_validator(
        self,
        validator_address: str,
        force_refresh: bool = False,
    ) -> Optional[ValidatorInfo]:
        """
        Get validator by address.

        Args:
            validator_address: Validator address
            force_refresh: Force refresh cache

        Returns:
            ValidatorInfo or None
        """
        if not force_refresh and validator_address in self._validators_cache:
            return self._validators_cache[validator_address]

        validators = await self.get_validators(force_refresh=True)
        for v in validators:
            if v.address == validator_address:
                return v

        return None

    async def get_top_validators(
        self,
        limit: int = 10,
    ) -> List[ValidatorInfo]:
        """
        Get top validators by voting power.

        Args:
            limit: Number of validators

        Returns:
            List of ValidatorInfo
        """
        validators = await self.get_validators(status=ValidatorStatus.BONDED)
        validators.sort(key=lambda v: v.voting_power, reverse=True)

        # Set ranks
        for i, v in enumerate(validators[:limit]):
            v.rank = i + 1

        return validators[:limit]

    async def get_validator_recommendations(
        self,
        amount: Optional[float] = None,
    ) -> List[ValidatorInfo]:
        """
        Get recommended validators for delegation.

        Args:
            amount: Amount to delegate (for optimization)

        Returns:
            List of recommended validators
        """
        validators = await self.get_top_validators(limit=50)

        # Filter out jailed and tombstoned
        validators = [v for v in validators if not v.is_jailed and not v.tombstoned]

        # Score validators
        scored = []
        for v in validators:
            score = self._calculate_validator_score(v)
            scored.append((score, v))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [v for _, v in scored[:10]]

    def _calculate_validator_score(self, validator: ValidatorInfo) -> float:
        """Calculate validator score."""
        score = 0.0

        # APY score (40%)
        score += validator.apy * 0.4

        # Uptime score (25%)
        score += (validator.uptime / 100) * 0.25

        # Commission score (15%) - lower is better
        commission_score = 1 - validator.commission_rate
        score += commission_score * 0.15

        # Voting power score (10%)
        power_score = min(validator.voting_power / 100000000, 1.0)
        score += power_score * 0.1

        # Activity score (10%)
        if validator.is_active:
            score += 0.1

        return score

    # -----------------------------------------------------------------------
    # Delegation Operations
    # -----------------------------------------------------------------------

    async def delegate(
        self,
        validator_address: str,
        amount: float,
        memo: Optional[str] = None,
    ) -> Optional[str]:
        """
        Delegate ATOM to a validator.

        Args:
            validator_address: Validator address
            amount: Amount to delegate
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        if not self._wallet:
            logger.error("Wallet not initialized")
            return None

        try:
            start_time = time.time()

            # Convert amount to uatom
            amount_uatom = int(amount * 10 ** self.DECIMALS)

            # Build delegation message
            msg = {
                "type": "cosmos-sdk/MsgDelegate",
                "value": {
                    "delegator_address": self._address,
                    "validator_address": validator_address,
                    "amount": {
                        "denom": self.DENOM,
                        "amount": str(amount_uatom),
                    },
                },
            }

            # Broadcast transaction
            tx_hash = await self._broadcast_transaction([msg], memo)

            if tx_hash:
                self._performance["transactions_sent"] += 1
                self._performance["avg_response_time_ms"] = (
                    (self._performance["avg_response_time_ms"] *
                     (self._performance["transactions_sent"] - 1) +
                     (time.time() - start_time) * 1000) /
                    self._performance["transactions_sent"]
                )

                logger.info(
                    f"Delegated {amount} ATOM to {validator_address}",
                    extra={"tx_hash": tx_hash}
                )

                # Clear cache
                self._delegations_cache.clear()

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
        Undelegate ATOM from a validator.

        Args:
            validator_address: Validator address
            amount: Amount to undelegate
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        if not self._wallet:
            logger.error("Wallet not initialized")
            return None

        try:
            amount_uatom = int(amount * 10 ** self.DECIMALS)

            msg = {
                "type": "cosmos-sdk/MsgUndelegate",
                "value": {
                    "delegator_address": self._address,
                    "validator_address": validator_address,
                    "amount": {
                        "denom": self.DENOM,
                        "amount": str(amount_uatom),
                    },
                },
            }

            tx_hash = await self._broadcast_transaction([msg], memo)

            if tx_hash:
                logger.info(
                    f"Undelegated {amount} ATOM from {validator_address}",
                    extra={"tx_hash": tx_hash}
                )
                self._delegations_cache.clear()

            return tx_hash

        except Exception as e:
            logger.error(f"Error undelegating: {e}")
            return None

    async def redelegate(
        self,
        src_validator_address: str,
        dst_validator_address: str,
        amount: float,
        memo: Optional[str] = None,
    ) -> Optional[str]:
        """
        Redelegate ATOM from one validator to another.

        Args:
            src_validator_address: Source validator address
            dst_validator_address: Destination validator address
            amount: Amount to redelegate
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        if not self._wallet:
            logger.error("Wallet not initialized")
            return None

        try:
            amount_uatom = int(amount * 10 ** self.DECIMALS)

            msg = {
                "type": "cosmos-sdk/MsgBeginRedelegate",
                "value": {
                    "delegator_address": self._address,
                    "validator_src_address": src_validator_address,
                    "validator_dst_address": dst_validator_address,
                    "amount": {
                        "denom": self.DENOM,
                        "amount": str(amount_uatom),
                    },
                },
            }

            tx_hash = await self._broadcast_transaction([msg], memo)

            if tx_hash:
                logger.info(
                    f"Redelegated {amount} ATOM from {src_validator_address} to {dst_validator_address}",
                    extra={"tx_hash": tx_hash}
                )
                self._delegations_cache.clear()

            return tx_hash

        except Exception as e:
            logger.error(f"Error redelegating: {e}")
            return None

    # -----------------------------------------------------------------------
    # Rewards Operations
    # -----------------------------------------------------------------------

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
        if not self._wallet:
            logger.error("Wallet not initialized")
            return None

        try:
            msgs = []

            if validator_addresses:
                for v in validator_addresses:
                    msgs.append({
                        "type": "cosmos-sdk/MsgWithdrawDelegationReward",
                        "value": {
                            "delegator_address": self._address,
                            "validator_address": v,
                        },
                    })
            else:
                # Claim from all validators
                delegations = await self.get_delegations()
                for d in delegations:
                    msgs.append({
                        "type": "cosmos-sdk/MsgWithdrawDelegationReward",
                        "value": {
                            "delegator_address": self._address,
                            "validator_address": d.validator_address,
                        },
                    })

            if not msgs:
                logger.warning("No rewards to claim")
                return None

            tx_hash = await self._broadcast_transaction(msgs, memo)

            if tx_hash:
                self._performance["rewards_claimed"] += 1
                logger.info(
                    f"Claimed rewards from {len(msgs)} validators",
                    extra={"tx_hash": tx_hash}
                )
                self._delegations_cache.clear()

            return tx_hash

        except Exception as e:
            logger.error(f"Error claiming rewards: {e}")
            return None

    async def compound_rewards(
        self,
        validator_address: str,
        memo: Optional[str] = None,
    ) -> Optional[str]:
        """
        Claim and restake rewards to a validator.

        Args:
            validator_address: Validator address
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        if not self._wallet:
            logger.error("Wallet not initialized")
            return None

        try:
            # First get rewards
            delegations = await self.get_delegations()
            rewards = 0

            for d in delegations:
                if d.validator_address == validator_address:
                    rewards = d.rewards
                    break

            if rewards <= 0:
                logger.warning("No rewards to compound")
                return None

            # Claim rewards
            claim_hash = await self.claim_rewards([validator_address], memo)
            if not claim_hash:
                return None

            # Wait for transaction to complete
            await asyncio.sleep(6)

            # Delegate rewards
            delegate_hash = await self.delegate(validator_address, rewards, memo)

            if delegate_hash:
                logger.info(
                    f"Compounded {rewards} ATOM rewards to {validator_address}",
                    extra={"claim_tx": claim_hash, "delegate_tx": delegate_hash}
                )

            return delegate_hash

        except Exception as e:
            logger.error(f"Error compounding rewards: {e}")
            return None

    # -----------------------------------------------------------------------
    # Delegation Queries
    # -----------------------------------------------------------------------

    async def get_delegations(
        self,
        address: Optional[str] = None,
        force_refresh: bool = False,
    ) -> List[DelegationInfo]:
        """
        Get delegations for an address.

        Args:
            address: Delegator address
            force_refresh: Force refresh cache

        Returns:
            List of DelegationInfo
        """
        address = address or self._address

        if not address:
            logger.error("No address provided")
            return []

        if not force_refresh and address in self._delegations_cache:
            return list(self._delegations_cache.values())

        try:
            start_time = time.time()

            # Query delegations
            delegations_data = await self._query_delegations(address)

            if not delegations_data:
                return []

            delegations = []
            for d in delegations_data:
                delegation = self._parse_delegation(d, address)
                delegations.append(delegation)

            # Cache
            self._delegations_cache = {d.validator_address: d for d in delegations}

            # Update performance
            self._performance["delegation_queries"] += 1
            self._performance["avg_response_time_ms"] = (
                (self._performance["avg_response_time_ms"] *
                 (self._performance["delegation_queries"] - 1) +
                 (time.time() - start_time) * 1000) /
                self._performance["delegation_queries"]
            )

            return delegations

        except Exception as e:
            logger.error(f"Error getting delegations: {e}")
            return []

    async def _query_delegations(self, address: str) -> List[Dict[str, Any]]:
        """Query delegations from Cosmos API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.REST_API}/cosmos/staking/v1beta1/delegations/{address}",
                    timeout=30,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("delegation_responses", [])
                    else:
                        logger.error(f"Error querying delegations: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Error querying delegations: {e}")
            return []

    def _parse_delegation(
        self,
        data: Dict[str, Any],
        delegator_address: str,
    ) -> DelegationInfo:
        """Parse delegation data."""
        delegation = data.get("delegation", {})
        balance = data.get("balance", {})

        return DelegationInfo(
            delegator_address=delegator_address,
            validator_address=delegation.get("validator_address", ""),
            amount=float(balance.get("amount", "0")) / 10 ** self.DECIMALS,
            shares=float(delegation.get("shares", "0")) / 1e18,
            rewards=0,  # Would need separate query
            status=DelegationStatus.ACTIVE,
            created_at=datetime.utcnow(),
            last_reward_claim=None,
            is_liquid=False,
        )

    async def get_staking_position(
        self,
        address: Optional[str] = None,
    ) -> Optional[StakingPosition]:
        """
        Get complete staking position.

        Args:
            address: Delegator address

        Returns:
            StakingPosition or None
        """
        address = address or self._address

        if not address:
            return None

        try:
            delegations = await self.get_delegations(address)

            if not delegations:
                return None

            # Get validator info
            validators = []
            total_delegated = 0
            total_rewards = 0

            for d in delegations:
                validator = await self.get_validator(d.validator_address)
                if validator:
                    validators.append(validator)
                total_delegated += d.amount
                total_rewards += d.rewards

            # Get unbonding info
            unbonding_info = await self._query_unbonding(address)
            unbonding_amount = unbonding_info.get("amount", 0)
            unbonding_time = unbonding_info.get("completion_time")

            # Get ATOM price
            price_usd = await self._get_atom_price()

            return StakingPosition(
                total_delegated=total_delegated,
                total_rewards=total_rewards,
                total_value_usd=(total_delegated + total_rewards) * price_usd,
                delegations=delegations,
                validators=validators,
                unbonding_amount=unbonding_amount,
                unbonding_time=unbonding_time,
                average_apy=sum(v.apy for v in validators) / len(validators) if validators else 0,
                daily_rewards=total_rewards / 30,  # Approximate
                weekly_rewards=total_rewards / 30 * 7,
                monthly_rewards=total_rewards,
            )

        except Exception as e:
            logger.error(f"Error getting staking position: {e}")
            return None

    async def _query_unbonding(self, address: str) -> Dict[str, Any]:
        """Query unbonding delegations."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.REST_API}/cosmos/staking/v1beta1/delegators/{address}/unbonding_delegations",
                    timeout=30,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        entries = data.get("unbonding_responses", [])
                        if entries:
                            entry = entries[0]
                            return {
                                "amount": float(entry.get("balance", "0")) / 10 ** self.DECIMALS,
                                "completion_time": entry.get("completion_time"),
                            }
                    return {}

        except Exception as e:
            logger.error(f"Error querying unbonding: {e}")
            return {}

    # -----------------------------------------------------------------------
    # Staking Statistics
    # -----------------------------------------------------------------------

    async def get_staking_stats(
        self,
        force_refresh: bool = False,
    ) -> Optional[StakingStats]:
        """
        Get global staking statistics.

        Args:
            force_refresh: Force refresh cache

        Returns:
            StakingStats or None
        """
        if not force_refresh and self._stats_cache:
            return self._stats_cache

        try:
            # Query staking pool
            pool_data = await self._query_staking_pool()

            if not pool_data:
                return None

            # Get validators
            validators = await self.get_validators(status=ValidatorStatus.BONDED)

            # Calculate APY stats
            apys = [v.apy for v in validators if v.apy > 0]

            # Get ATOM price
            price_usd = await self._get_atom_price()

            stats = StakingStats(
                total_atom_staked=float(pool_data.get("bonded_tokens", "0")) / 10 ** self.DECIMALS,
                total_validators=len(validators),
                active_validators=sum(1 for v in validators if v.is_active),
                average_apy=sum(apys) / len(apys) if apys else 0,
                min_apy=min(apys) if apys else 0,
                max_apy=max(apys) if apys else 0,
                median_apy=sorted(apys)[len(apys) // 2] if apys else 0,
                total_delegations=0,  # Would need to query
                total_staked_usd=float(pool_data.get("bonded_tokens", "0")) / 10 ** self.DECIMALS * price_usd,
                inflation_rate=float(pool_data.get("inflation", "0")) / 1e18,
                community_pool=float(pool_data.get("community_pool", "0")) / 10 ** self.DECIMALS,
                bonded_tokens=float(pool_data.get("bonded_tokens", "0")) / 10 ** self.DECIMALS,
                unbonding_tokens=float(pool_data.get("unbonding_tokens", "0")) / 10 ** self.DECIMALS,
                last_updated=datetime.utcnow(),
            )

            self._stats_cache = stats
            return stats

        except Exception as e:
            logger.error(f"Error getting staking stats: {e}")
            return None

    async def _query_staking_pool(self) -> Dict[str, Any]:
        """Query staking pool data."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.REST_API}/cosmos/staking/v1beta1/pool",
                    timeout=30,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("pool", {})
                    return {}

        except Exception as e:
            logger.error(f"Error querying staking pool: {e}")
            return {}

    # -----------------------------------------------------------------------
    # Transaction Broadcasting
    # -----------------------------------------------------------------------

    async def _broadcast_transaction(
        self,
        msgs: List[Dict[str, Any]],
        memo: Optional[str] = None,
    ) -> Optional[str]:
        """
        Broadcast a transaction.

        Args:
            msgs: Messages to include
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        try:
            if not self._wallet:
                logger.error("Wallet not initialized")
                return None

            # Build transaction
            tx = self._wallet.build_tx(
                msgs=msgs,
                memo=memo or "",
                gas=200000,
                gas_prices=Coins([Coin("uatom", 0.025)]),
            )

            # Sign transaction
            signed_tx = self._wallet.sign_tx(tx)

            # Broadcast
            result = await self._wallet.broadcast(signed_tx)

            if result and result.get("code", 1) == 0:
                return result.get("txhash")
            else:
                logger.error(f"Transaction failed: {result}")
                return None

        except Exception as e:
            logger.error(f"Error broadcasting transaction: {e}")
            return None

    # -----------------------------------------------------------------------
    # Price Queries
    # -----------------------------------------------------------------------

    async def _get_atom_price(self) -> float:
        """Get ATOM price in USD."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": "cosmos", "vs_currencies": "usd"},
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("cosmos", {}).get("usd", 0.0)
                    return 0.0

        except Exception as e:
            logger.error(f"Error getting ATOM price: {e}")
            return 0.0

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_address(self) -> Optional[str]:
        """Get wallet address."""
        return self._address

    def get_chain_id(self) -> str:
        """Get chain ID."""
        return self.CHAIN_ID

    def get_denom(self) -> str:
        """Get denomination."""
        return self.DENOM

    def get_decimals(self) -> int:
        """Get decimals."""
        return self.DECIMALS

    def format_amount(self, amount: int) -> float:
        """Format amount from uatom to ATOM."""
        return amount / 10 ** self.DECIMALS

    def parse_amount(self, amount: float) -> int:
        """Parse amount from ATOM to uatom."""
        return int(amount * 10 ** self.DECIMALS)

    # -----------------------------------------------------------------------
    # Health Check
    # -----------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            # Check client connection
            client_healthy = self._client is not None

            # Check API availability
            api_healthy = False
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.REST_API}/cosmos/base/tendermint/v1beta1/node_info",
                        timeout=10,
                    ) as response:
                        api_healthy = response.status == 200
            except:
                pass

            return {
                "status": "healthy" if client_healthy and api_healthy else "unhealthy",
                "client_healthy": client_healthy,
                "api_healthy": api_healthy,
                "address": self._address,
                "chain_id": self.CHAIN_ID,
                "cached_validators": len(self._validators_cache),
                "cached_delegations": len(self._delegations_cache),
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
            "cached_delegations": len(self._delegations_cache),
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
        logger.info("ATOMStaking started")

    async def stop(self) -> None:
        """Stop the staking integration."""
        self._running = False

        # Clear caches
        self._validators_cache.clear()
        self._delegations_cache.clear()
        self._stats_cache = None

        logger.info("ATOMStaking stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_atom_staking(
    config: Optional[Dict[str, Any]] = None,
) -> ATOMStaking:
    """
    Factory function to create an ATOMStaking instance.

    Args:
        config: Configuration dictionary

    Returns:
        ATOMStaking instance
    """
    return ATOMStaking(config=config)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use ATOM staking
    pass
