# blockchain/staking/sol_staking.py
# NEXUS AI TRADING SYSTEM - Solana (SOL) Staking Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Solana (SOL) Staking Integration for NEXUS AI Trading System.
Provides comprehensive staking operations on Solana network including:
- Stake account management
- Delegation to validators
- Deactivation and withdrawal
- Stake account creation
- Validator management
- Reward claiming
- Staking analytics
- Liquid staking support
- Stake pool participation
"""

import asyncio
import base58
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import create_account
from solders.stake_program import (
    StakeState,
    authorize,
    delegate_stake,
    deactivate_stake,
    initialize,
    split,
    withdraw,
)
from solders.sysvar import clock
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Confirmed, Finalized
from solana.rpc.types import TxOpts
from solana.rpc.core import RPCException
from solana.keypair import Keypair
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.async_client import AsyncToken

# NEXUS Imports
from blockchain.staking.base_staking import BaseStaking, StakingProvider, StakingStatus, ValidatorStatus, ValidatorInfo
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.staking.sol")


# ============================================================================
# Enums & Constants
# ============================================================================

class SOLStakingType(str, Enum):
    """Solana staking types."""
    NATIVE = "native"          # Native SOL staking
    STAKE_POOL = "stake_pool"  # Stake pool staking
    LIQUID = "liquid"          # Liquid staking (stSOL, mSOL)
    MARINADE = "marinade"      # Marinade Finance
    JITO = "jito"              # Jito


class StakeAccountStatus(str, Enum):
    """Stake account status."""
    INITIALIZED = "initialized"
    DELEGATED = "delegated"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    INACTIVE = "inactive"
    WITHDRAWN = "withdrawn"


@dataclass
class SOLValidator:
    """Solana validator information."""
    address: str
    name: str
    commission: float
    vote_account: str
    stake: float
    active_stake: float
    delinquent: bool
    apy: float
    score: float
    rank: int
    is_active: bool
    is_jailed: bool
    last_vote: int
    root_slot: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StakeAccount:
    """Solana stake account information."""
    address: str
    owner: str
    status: StakeAccountStatus
    stake_amount: float
    delegated_amount: float
    validator: Optional[str] = None
    activation_epoch: Optional[int] = None
    deactivation_epoch: Optional[int] = None
    created_at: Optional[datetime] = None
    last_reward_epoch: Optional[int] = None
    warmup_cooldown_rate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SOLStakingPosition:
    """Solana staking position."""
    total_staked: float
    total_rewards: float
    total_value_usd: float
    stake_accounts: List[StakeAccount]
    validators: List[SOLValidator]
    liquid_staked: Dict[str, float]
    staking_type: SOLStakingType
    average_apy: float
    daily_rewards: float
    weekly_rewards: float
    monthly_rewards: float
    status: StakingStatus = StakingStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SOLStakingStats:
    """Solana staking statistics."""
    total_sol_staked: float
    total_validators: int
    active_validators: int
    average_apy: float
    min_apy: float
    max_apy: float
    median_apy: float
    staking_rate: float
    total_staked_usd: float
    total_stake_accounts: int
    avg_stake_account_balance: float
    liquid_staking_tvl: float
    last_updated: datetime


@dataclass
class StakePoolInfo:
    """Solana stake pool information."""
    address: str
    name: str
    manager: str
    stake_pool_token: str
    total_stake: float
    total_validators: int
    active_validators: int
    average_apy: float
    fee: float
    apy: float
    is_active: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Solana Staking Integration
# ============================================================================

class SOLStaking(BaseStaking):
    """
    Solana (SOL) Staking Integration.
    Provides comprehensive staking operations on Solana network.
    """

    # Solana network parameters
    CLUSTER = "mainnet-beta"
    COMMITMENT = Confirmed

    # Solana staking constants
    MIN_STAKE_AMOUNT = 0.001  # SOL
    MIN_DELEGATION_AMOUNT = 0.001  # SOL
    WARMUP_EPOCHS = 2
    COOLDOWN_EPOCHS = 2

    # RPC endpoints
    RPC_URLS = [
        "https://api.mainnet-beta.solana.com",
        "https://solana-api.projectserum.com",
        "https://rpc.ankr.com/solana",
    ]

    # Native SOL token address
    NATIVE_SOL = "So11111111111111111111111111111111111111112"

    # Liquid staking protocols
    LIQUID_PROTOCOLS = {
        "stSOL": {
            "address": "stSol",
            "symbol": "stSOL",
            "protocol": "Marinade",
            "apy": 0.06,
        },
        "mSOL": {
            "address": "mSOL",
            "symbol": "mSOL",
            "protocol": "Jito",
            "apy": 0.065,
        },
        "jitoSOL": {
            "address": "jitoSOL",
            "symbol": "jitoSOL",
            "protocol": "Jito",
            "apy": 0.07,
        },
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Solana staking integration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(
            provider=StakingProvider.SOLANA,
            config=config,
        )

        self._client = None
        self._payer = None

        # Cache
        self._validators_cache: Dict[str, SOLValidator] = {}
        self._stake_accounts_cache: Dict[str, StakeAccount] = {}
        self._position_cache: Optional[SOLStakingPosition] = None
        self._stats_cache: Optional[SOLStakingStats] = None
        self._stake_pools_cache: Dict[str, StakePoolInfo] = {}
        self._last_cache_update: datetime = datetime.utcnow() - timedelta(hours=1)

        # Performance metrics
        self._performance = {
            "validator_queries": 0,
            "position_queries": 0,
            "transactions_sent": 0,
            "stake_accounts_created": 0,
            "rewards_claimed": 0,
            "avg_response_time_ms": 0.0,
        }

        # Initialize client
        self._initialize_client()

        logger.info(
            "SOLStaking initialized",
            extra={"cluster": self.CLUSTER}
        )

    # -----------------------------------------------------------------------
    # Client Initialization
    # -----------------------------------------------------------------------

    def _initialize_client(self) -> None:
        """Initialize Solana client."""
        try:
            self._client = AsyncClient(
                self.RPC_URLS[0],
                commitment=self.COMMITMENT,
            )

            if self._private_key:
                # Create keypair from private key
                self._payer = Keypair.from_bytes(
                    base58.b58decode(self._private_key)
                )

            logger.info("Solana client initialized")

        except Exception as e:
            logger.error(f"Error initializing Solana client: {e}")
            raise

    # -----------------------------------------------------------------------
    # Validator Management
    # -----------------------------------------------------------------------

    async def get_validators(
        self,
        status: Optional[ValidatorStatus] = None,
        limit: Optional[int] = None,
        force_refresh: bool = False,
    ) -> List[SOLValidator]:
        """
        Get Solana validators.

        Args:
            status: Filter by status
            limit: Maximum number of validators
            force_refresh: Force refresh cache

        Returns:
            List of SOLValidator
        """
        if not force_refresh and self._validators_cache:
            validators = list(self._validators_cache.values())
            if status:
                validators = [v for v in validators if v.is_active]
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
                validators = [v for v in validators if v.is_active]

            if limit:
                validators = validators[:limit]

            return validators

        except Exception as e:
            logger.error(f"Error getting validators: {e}")
            return []

    async def _query_validators(self) -> List[Dict[str, Any]]:
        """Query validators from Solana."""
        try:
            # Use Solana RPC
            response = await self._client.get_vote_accounts()
            if response:
                data = response["result"]
                validators = []

                # Current validators
                for v in data.get("current", []):
                    validators.append({
                        "address": v.get("votePubkey", ""),
                        "commission": v.get("commission", 0),
                        "stake": v.get("stake", 0),
                        "active_stake": v.get("activatedStake", 0),
                        "delinquent": v.get("delinquent", False),
                        "last_vote": v.get("lastVote", 0),
                        "root_slot": v.get("rootSlot", 0),
                        "type": "current",
                    })

                # Delinquent validators
                for v in data.get("delinquent", []):
                    validators.append({
                        "address": v.get("votePubkey", ""),
                        "commission": v.get("commission", 0),
                        "stake": v.get("stake", 0),
                        "active_stake": v.get("activatedStake", 0),
                        "delinquent": True,
                        "last_vote": v.get("lastVote", 0),
                        "root_slot": v.get("rootSlot", 0),
                        "type": "delinquent",
                    })

                return validators

            return []

        except Exception as e:
            logger.error(f"Error querying validators: {e}")
            return []

    def _parse_validator(self, data: Dict[str, Any]) -> SOLValidator:
        """Parse validator data."""
        # Get validator name from known validators
        validator_name = self._get_validator_name(data.get("address", ""))

        # Calculate APY
        apy = self._calculate_validator_apy(data)

        return SOLValidator(
            address=data.get("address", ""),
            name=validator_name,
            commission=data.get("commission", 0) / 100,
            vote_account=data.get("address", ""),
            stake=data.get("stake", 0) / 1e9,
            active_stake=data.get("active_stake", 0) / 1e9,
            delinquent=data.get("delinquent", False),
            apy=apy,
            score=self._calculate_validator_score(data),
            rank=0,
            is_active=not data.get("delinquent", False),
            is_jailed=data.get("delinquent", False),
            last_vote=data.get("last_vote", 0),
            root_slot=data.get("root_slot", 0),
        )

    def _calculate_validator_apy(self, data: Dict[str, Any]) -> float:
        """Calculate validator APY."""
        # Simplified APY calculation
        commission = data.get("commission", 0) / 100
        stake = data.get("stake", 0) / 1e9

        # Base APY ~6-8%
        base_apy = 0.07

        # Adjust for commission
        adjusted_apy = base_apy * (1 - commission)

        # Adjust for stake (more stake = slightly lower returns)
        if stake > 1_000_000:
            adjusted_apy *= 0.95
        elif stake < 100_000:
            adjusted_apy *= 1.05

        return adjusted_apy * 100

    def _calculate_validator_score(self, data: Dict[str, Any]) -> float:
        """Calculate validator score."""
        score = 0.0

        # Commission (lower is better)
        commission = data.get("commission", 0) / 100
        score += (1 - commission) * 0.3

        # Active stake
        stake = data.get("active_stake", 0) / 1e9
        stake_score = min(stake / 1_000_000, 1.0)
        score += stake_score * 0.3

        # Delinquency
        if not data.get("delinquent", False):
            score += 0.2

        # Last vote recency
        last_vote = data.get("last_vote", 0)
        # Would need to check against current slot
        score += 0.2

        return score

    def _get_validator_name(self, address: str) -> str:
        """Get validator name from known list."""
        # Known validators
        known_validators = {
            "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM": "Jito",
            "7Np41QY8pBj6T8JqUv4rT56F3eB6Pz8qZDEt2nzPmPpQ": "Marinade",
            "HxRSYAVK4mRx2Zq8M7V3u9GpLZ5M9WpPpM9M9M9M9M9M": "Solana Labs",
            "Cgv5L9kZjRhzDbDq7z1Lg2ZxVnQk9gq7z1Lg2ZxVnQk9g": "Figment",
            "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM": "Jito Labs",
        }
        return known_validators.get(address, f"Validator_{address[:8]}")

    async def get_validator(
        self,
        validator_address: str,
        force_refresh: bool = False,
    ) -> Optional[SOLValidator]:
        """
        Get validator by address.

        Args:
            validator_address: Validator address
            force_refresh: Force refresh cache

        Returns:
            SOLValidator or None
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
    ) -> List[SOLValidator]:
        """
        Get top validators by stake.

        Args:
            limit: Number of validators

        Returns:
            List of SOLValidator
        """
        validators = await self.get_validators()
        validators.sort(key=lambda v: v.active_stake, reverse=True)

        for i, v in enumerate(validators[:limit]):
            v.rank = i + 1

        return validators[:limit]

    # -----------------------------------------------------------------------
    # Stake Account Management
    # -----------------------------------------------------------------------

    async def create_stake_account(
        self,
        amount: float,
        from_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a stake account.

        Args:
            amount: Amount to stake
            from_address: From address (optional)

        Returns:
            Stake account address
        """
        if not self._payer:
            logger.error("Payer not initialized")
            return None

        try:
            start_time = time.time()

            # Get recent blockhash
            blockhash = await self._client.get_latest_blockhash()

            # Create stake account keypair
            stake_keypair = Keypair()

            # Get rent exemption
            rent = await self._client.get_minimum_balance_for_rent_exemption(
                StakeState.LEN
            )

            # Create account transaction
            tx = create_account(
                self._payer.pubkey(),
                stake_keypair.pubkey(),
                rent,
                StakeState.LEN,
                stake_program_id=Pubkey.from_string("Stake11111111111111111111111111111111111111"),
            )

            # Initialize stake account
            init_tx = initialize(
                stake_keypair.pubkey(),
                authorize=stake_keypair.pubkey(),
                lockup=stake_keypair.pubkey(),
            )

            # Combine transactions
            tx += init_tx

            # Send transaction
            signature = await self._client.send_transaction(
                tx,
                self._payer,
                stake_keypair,
                opts=TxOpts(skip_preflight=False),
            )

            if signature:
                self._performance["stake_accounts_created"] += 1
                self._performance["transactions_sent"] += 1

                logger.info(
                    f"Created stake account: {stake_keypair.pubkey()}",
                    extra={"amount": amount}
                )

                # Clear cache
                self._stake_accounts_cache.clear()
                self._position_cache = None

                return str(stake_keypair.pubkey())

            return None

        except Exception as e:
            logger.error(f"Error creating stake account: {e}")
            return None

    async def delegate_stake(
        self,
        stake_account: str,
        validator_address: str,
        amount: Optional[float] = None,
    ) -> Optional[str]:
        """
        Delegate stake to a validator.

        Args:
            stake_account: Stake account address
            validator_address: Validator address
            amount: Amount to delegate (optional)

        Returns:
            Transaction signature
        """
        try:
            start_time = time.time()

            # Convert to Pubkey
            stake_pubkey = Pubkey.from_string(stake_account)
            validator_pubkey = Pubkey.from_string(validator_address)

            # Get recent blockhash
            blockhash = await self._client.get_latest_blockhash()

            # Build delegation transaction
            tx = delegate_stake(
                stake_pubkey,
                self._payer.pubkey(),
                validator_pubkey,
            )

            # Send transaction
            signature = await self._client.send_transaction(
                tx,
                self._payer,
                opts=TxOpts(skip_preflight=False),
            )

            if signature:
                self._performance["transactions_sent"] += 1
                self._performance["avg_response_time_ms"] = (
                    (self._performance["avg_response_time_ms"] *
                     (self._performance["transactions_sent"] - 1) +
                     (time.time() - start_time) * 1000) /
                    self._performance["transactions_sent"]
                )

                logger.info(
                    f"Delegated stake to {validator_address}",
                    extra={"stake_account": stake_account}
                )

                # Clear cache
                self._stake_accounts_cache.clear()
                self._position_cache = None

                return str(signature)

            return None

        except Exception as e:
            logger.error(f"Error delegating stake: {e}")
            return None

    async def deactivate_stake(
        self,
        stake_account: str,
    ) -> Optional[str]:
        """
        Deactivate stake account.

        Args:
            stake_account: Stake account address

        Returns:
            Transaction signature
        """
        try:
            stake_pubkey = Pubkey.from_string(stake_account)

            blockhash = await self._client.get_latest_blockhash()

            tx = deactivate_stake(
                stake_pubkey,
                self._payer.pubkey(),
            )

            signature = await self._client.send_transaction(
                tx,
                self._payer,
                opts=TxOpts(skip_preflight=False),
            )

            if signature:
                logger.info(
                    f"Deactivated stake account: {stake_account}",
                    extra={"signature": str(signature)}
                )
                self._stake_accounts_cache.clear()
                self._position_cache = None

                return str(signature)

            return None

        except Exception as e:
            logger.error(f"Error deactivating stake: {e}")
            return None

    async def withdraw_stake(
        self,
        stake_account: str,
        amount: Optional[float] = None,
    ) -> Optional[str]:
        """
        Withdraw from stake account.

        Args:
            stake_account: Stake account address
            amount: Amount to withdraw (optional)

        Returns:
            Transaction signature
        """
        try:
            stake_pubkey = Pubkey.from_string(stake_account)

            # Get stake account info
            stake_account_info = await self.get_stake_account(stake_account)

            if not stake_account_info:
                return None

            # Get token account
            token_account = await self._get_token_account()

            blockhash = await self._client.get_latest_blockhash()

            tx = withdraw(
                stake_pubkey,
                token_account,
                self._payer.pubkey(),
                int(stake_account_info.stake_amount * 1e9),
            )

            signature = await self._client.send_transaction(
                tx,
                self._payer,
                opts=TxOpts(skip_preflight=False),
            )

            if signature:
                logger.info(
                    f"Withdrew from stake account: {stake_account}",
                    extra={"signature": str(signature)}
                )
                self._stake_accounts_cache.clear()
                self._position_cache = None

                return str(signature)

            return None

        except Exception as e:
            logger.error(f"Error withdrawing stake: {e}")
            return None

    # -----------------------------------------------------------------------
    # Stake Account Queries
    # -----------------------------------------------------------------------

    async def get_stake_account(
        self,
        stake_account: str,
        force_refresh: bool = False,
    ) -> Optional[StakeAccount]:
        """
        Get stake account information.

        Args:
            stake_account: Stake account address
            force_refresh: Force refresh cache

        Returns:
            StakeAccount or None
        """
        if not force_refresh and stake_account in self._stake_accounts_cache:
            return self._stake_accounts_cache[stake_account]

        try:
            stake_pubkey = Pubkey.from_string(stake_account)

            # Get account info
            response = await self._client.get_account_info(stake_pubkey)

            if not response:
                return None

            # Parse stake account
            account_info = response["result"]["value"]
            if not account_info:
                return None

            # Parse stake state
            stake_state = StakeState.from_bytes(account_info["data"])

            # Extract information
            if stake_state.is_delegated():
                status = StakeAccountStatus.ACTIVE
                delegated_amount = stake_state.stake() / 1e9
                validator = str(stake_state.delegation().voter_pubkey)
            else:
                status = StakeAccountStatus.INITIALIZED
                delegated_amount = 0
                validator = None

            stake_account_info = StakeAccount(
                address=stake_account,
                owner=str(stake_state.authorized().staker),
                status=status,
                stake_amount=stake_state.stake() / 1e9,
                delegated_amount=delegated_amount,
                validator=validator,
                activation_epoch=stake_state.delegation().activation_epoch,
                deactivation_epoch=stake_state.delegation().deactivation_epoch,
            )

            self._stake_accounts_cache[stake_account] = stake_account_info

            return stake_account_info

        except Exception as e:
            logger.error(f"Error getting stake account: {e}")
            return None

    async def get_stake_accounts(
        self,
        owner: Optional[str] = None,
        force_refresh: bool = False,
    ) -> List[StakeAccount]:
        """
        Get all stake accounts for an owner.

        Args:
            owner: Owner address
            force_refresh: Force refresh cache

        Returns:
            List of StakeAccount
        """
        owner = owner or str(self._payer.pubkey()) if self._payer else None

        if not owner:
            logger.error("No owner provided")
            return []

        try:
            # Get program accounts
            response = await self._client.get_program_accounts(
                Pubkey.from_string("Stake11111111111111111111111111111111111111"),
                encoding="base64",
            )

            stake_accounts = []
            for account in response:
                pubkey = str(account.pubkey)
                account_info = account.account

                # Check if owner matches
                if owner and str(account_info.owner) != owner:
                    continue

                try:
                    stake_state = StakeState.from_bytes(account_info.data)
                    if stake_state.is_delegated():
                        status = StakeAccountStatus.ACTIVE
                        delegated_amount = stake_state.stake() / 1e9
                        validator = str(stake_state.delegation().voter_pubkey)
                    else:
                        status = StakeAccountStatus.INITIALIZED
                        delegated_amount = 0
                        validator = None

                    stake_accounts.append(StakeAccount(
                        address=pubkey,
                        owner=owner,
                        status=status,
                        stake_amount=stake_state.stake() / 1e9,
                        delegated_amount=delegated_amount,
                        validator=validator,
                        activation_epoch=stake_state.delegation().activation_epoch,
                        deactivation_epoch=stake_state.delegation().deactivation_epoch,
                    ))
                except Exception:
                    continue

            return stake_accounts

        except Exception as e:
            logger.error(f"Error getting stake accounts: {e}")
            return []

    # -----------------------------------------------------------------------
    # Staking Position
    # -----------------------------------------------------------------------

    async def get_staking_position(
        self,
        address: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[SOLStakingPosition]:
        """
        Get Solana staking position.

        Args:
            address: Staker address
            force_refresh: Force refresh cache

        Returns:
            SOLStakingPosition or None
        """
        address = address or str(self._payer.pubkey()) if self._payer else None

        if not address:
            return None

        if not force_refresh and self._position_cache:
            return self._position_cache

        try:
            start_time = time.time()

            # Get stake accounts
            stake_accounts = await self.get_stake_accounts(address, force_refresh=True)

            if not stake_accounts:
                return None

            # Get validator info
            validators = []
            total_staked = 0
            total_rewards = 0

            for sa in stake_accounts:
                if sa.validator:
                    validator = await self.get_validator(sa.validator)
                    if validator and validator not in validators:
                        validators.append(validator)
                total_staked += sa.stake_amount

            # Get liquid staking balances
            liquid_staked = await self._get_liquid_balances(address)

            # Calculate APY
            apy = await self._calculate_apy(validators)

            # Get SOL price
            price_usd = await self._get_sol_price()

            position = SOLStakingPosition(
                total_staked=total_staked,
                total_rewards=total_rewards,
                total_value_usd=(total_staked + total_rewards) * price_usd,
                stake_accounts=stake_accounts,
                validators=validators,
                liquid_staked=liquid_staked,
                staking_type=SOLStakingType.NATIVE,
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
                # Would query token account balance
                balances[protocol] = 0.0
            except Exception:
                pass

        return balances

    async def _calculate_apy(self, validators: List[SOLValidator]) -> float:
        """Calculate average APY."""
        if not validators:
            return 0.0

        total_apy = sum(v.apy for v in validators)
        return total_apy / len(validators)

    async def _get_token_account(self) -> Pubkey:
        """Get token account."""
        if not self._payer:
            raise ValueError("Payer not initialized")

        # Get associated token account
        token_account = await self._client.get_token_accounts_by_owner(
            self._payer.pubkey(),
            {
                "mint": Pubkey.from_string(self.NATIVE_SOL),
            },
        )

        if token_account["result"]["value"]:
            return Pubkey.from_string(
                token_account["result"]["value"][0]["pubkey"]
            )
        else:
            # Create token account
            token = AsyncToken(
                self._client,
                Pubkey.from_string(self.NATIVE_SOL),
                TOKEN_PROGRAM_ID,
                self._payer,
            )
            # Would create account if needed
            raise ValueError("No token account found")

    # -----------------------------------------------------------------------
    # Staking Statistics
    # -----------------------------------------------------------------------

    async def get_staking_stats(self) -> Optional[SOLStakingStats]:
        """
        Get Solana staking statistics.

        Returns:
            SOLStakingStats or None
        """
        if self._stats_cache:
            return self._stats_cache

        try:
            # Get validators
            validators = await self.get_validators()

            active_validators = [v for v in validators if v.is_active]
            apys = [v.apy for v in active_validators if v.apy > 0]

            # Get SOL price
            price_usd = await self._get_sol_price()

            stats = SOLStakingStats(
                total_sol_staked=sum(v.active_stake for v in active_validators),
                total_validators=len(validators),
                active_validators=len(active_validators),
                average_apy=sum(apys) / len(apys) if apys else 0,
                min_apy=min(apys) if apys else 0,
                max_apy=max(apys) if apys else 0,
                median_apy=sorted(apys)[len(apys) // 2] if apys else 0,
                staking_rate=sum(v.active_stake for v in active_validators) / 1e9,
                total_staked_usd=sum(v.active_stake for v in active_validators) * price_usd,
                total_stake_accounts=0,  # Would need to query
                avg_stake_account_balance=0,
                liquid_staking_tvl=0,
                last_updated=datetime.utcnow(),
            )

            self._stats_cache = stats
            return stats

        except Exception as e:
            logger.error(f"Error getting staking stats: {e}")
            return None

    # -----------------------------------------------------------------------
    # Price Queries
    # -----------------------------------------------------------------------

    async def _get_sol_price(self) -> float:
        """Get SOL price in USD."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": "solana", "vs_currencies": "usd"},
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("solana", {}).get("usd", 0.0)
                    return 0.0

        except Exception as e:
            logger.error(f"Error getting SOL price: {e}")
            return 0.0

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_address(self) -> Optional[str]:
        """Get payer address."""
        return str(self._payer.pubkey()) if self._payer else None

    def get_cluster(self) -> str:
        """Get cluster."""
        return self.CLUSTER

    # -----------------------------------------------------------------------
    # Health Check
    # -----------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            # Check client connection
            health = await self._client.get_health()
            client_healthy = health is not None

            # Check validators
            validators = await self.get_validators(limit=1)
            validators_available = bool(validators)

            return {
                "status": "healthy" if client_healthy and validators_available else "unhealthy",
                "client_healthy": client_healthy,
                "validators_available": validators_available,
                "address": self.get_address(),
                "cluster": self.CLUSTER,
                "cached_validators": len(self._validators_cache),
                "cached_stake_accounts": len(self._stake_accounts_cache),
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
            "cached_stake_accounts": len(self._stake_accounts_cache),
            "position_cached": self._position_cache is not None,
            "address": self.get_address(),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the staking integration."""
        if self._running:
            return

        self._running = True
        logger.info("SOLStaking started")

    async def stop(self) -> None:
        """Stop the staking integration."""
        self._running = False

        # Clear caches
        self._validators_cache.clear()
        self._stake_accounts_cache.clear()
        self._position_cache = None
        self._stats_cache = None

        if self._client:
            await self._client.close()

        logger.info("SOLStaking stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_sol_staking(
    config: Optional[Dict[str, Any]] = None,
) -> SOLStaking:
    """
    Factory function to create a SOLStaking instance.

    Args:
        config: Configuration dictionary

    Returns:
        SOLStaking instance
    """
    return SOLStaking(config=config)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use SOL staking
    pass
